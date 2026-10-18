"""The research pipeline: identity → plan → search → extract → verify → rules → dig deeper → report.

Entry point for the chatbot/UI: :func:`run_research`.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, TypeVar, cast

from .budget import Budget
from .config import AgentConfig, Allowlist, ConfigError, load_all, load_prompt
from .identity import _norm_name, resolve_identity
from .llm import LLM, AnthropicLLM, LLMError
from .models import (
    UMBRELLAS,
    CandidateFactOut,
    ConfirmedEntity,
    ExtractOutput,
    Flag,
    Followup,
    FollowupOutput,
    IdentityOutput,
    PlannedSearch,
    PlanOutput,
    ProgressEvent,
    RejectedFact,
    ResearchResult,
    Source,
    SummaryOutput,
    TierId,
    UmbrellaId,
    VerifyOutput,
)
from .report import plural
from .report import render_markdown  # noqa: F401  (re-exported for convenience)
from .rules import area_statuses, classify, next_steps, overall_verdict, sort_flags
from .search import SearchClient, SearchError, SearchHit, SearchRequest, TavilyClient
from .untrusted import UNTRUSTED_NOTICE, wrap_untrusted
from .verification import quote_in_text, trim_quote

ProgressCallback = Callable[[ProgressEvent], None]


class _Timeout(Exception):
    pass


@dataclass
class _Page:
    source: Source
    text: str


@dataclass
class _State:
    cfg: AgentConfig
    llm: LLM
    search: SearchClient
    budget: Budget
    today: date
    now_iso: str
    on_progress: ProgressCallback | None
    result: ResearchResult
    allowlist: Allowlist
    entity: ConfirmedEntity | None = None
    seen_urls: set[str] = field(default_factory=set)
    sources: dict[str, Source] = field(default_factory=dict)
    flags: list[Flag] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    closed: bool = False  # set on timeout; late worker threads must not change the result
    _src_n: int = 0
    _flag_n: int = 0

    # -- helpers ---------------------------------------------------------
    def emit(self, kind: str, message: str, **data: Any) -> None:
        force = bool(data.pop("force", False))
        if self.closed and kind not in ("done", "report") and not force:
            return  # late events from abandoned worker threads
        ev = ProgressEvent(kind=cast(Any, kind), message=message, data=data, elapsed_s=round(self.budget.elapsed(), 2))
        with self.lock:
            self.result.trail.append(ev)
        if self.on_progress:
            try:
                self.on_progress(ev)
            except Exception:  # a broken UI callback must not break research
                pass

    def warn(self, message: str) -> None:
        with self.lock:
            self.result.warnings.append(message)
        self.emit("warning", message)

    def new_source_id(self) -> str:
        with self.lock:
            self._src_n += 1
            return f"S{self._src_n}"

    def new_flag_id(self) -> str:
        with self.lock:
            self._flag_n += 1
            return f"F{self._flag_n}"

    def check_time(self) -> None:
        if self.budget.expired():
            raise _Timeout()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_research(
    company: str,
    country: str | None = None,
    website: str | None = None,
    on_progress: ProgressCallback | None = None,
    *,
    llm: LLM | None = None,
    search: SearchClient | None = None,
    config: AgentConfig | None = None,
    today: date | None = None,
    clock: Callable[[], float] | None = None,
) -> ResearchResult:
    """Research a named company and return a structured, source-linked risk result.

    ``status`` is one of:
      * ``ok``                  – finished within budget
      * ``partial``             – stopped by the time limit; findings so far are returned
      * ``needs_clarification`` – several companies match; show ``clarification.question`` and
                                  the candidates, then call again with country and/or website
      * ``error``               – could not run (missing keys, config error); see ``warnings``
    """
    now = datetime.now(UTC)
    today = today or now.date()
    result = ResearchResult(
        status="ok", company_input=company, country_input=country, website_input=website,
        researched_at=now.isoformat(timespec="seconds") if today == now.date() else f"{today.isoformat()}T00:00:00+00:00",
    )
    try:
        cfg = config or load_all()
    except ConfigError as exc:
        result.status = "error"
        result.warnings.append(str(exc))
        return result

    if llm is None or search is None:
        try:
            llm, search = build_live_clients(cfg, llm, search)
        except (LLMError, SearchError) as exc:
            result.status = "error"
            result.warnings.append(str(exc))
            return result

    budget = Budget(cfg.settings.budget, clock=clock) if clock else Budget(cfg.settings.budget)
    result.models = {"gatherer": llm.model_name("gatherer"), "verifier": llm.model_name("verifier")}
    st = _State(cfg=cfg, llm=llm, search=search, budget=budget, today=today, now_iso=result.researched_at,
                on_progress=on_progress, result=result, allowlist=cfg.allowlist)

    try:
        _pipeline(st, company.strip(), (country or "").strip() or None, (website or "").strip() or None)
    except _Timeout:
        result.status = "partial"
        with st.lock:
            st.closed = True
        msg = f"Time limit of {cfg.settings.budget.wall_clock_seconds:.0f} s reached; returning partial results."
        result.warnings.append(msg)
        st.emit("warning", msg, force=True)
        if st.entity is not None:
            _finalise(st, write_summary=False)
    result.stats.searches_used = budget.searches
    result.stats.extracts_used = budget.extracts
    result.stats.followups_used = budget.followups
    result.stats.elapsed_s = round(budget.elapsed(), 2)
    st.emit("done", f"Research finished with status '{result.status}'.", status=result.status)
    return result


def build_live_clients(cfg: AgentConfig, llm: LLM | None = None, search: SearchClient | None = None) -> tuple[LLM, SearchClient]:
    """Create the real Claude + Tavily clients from environment variables."""
    s = cfg.settings
    if llm is None:
        llm = AnthropicLLM(s.models.gatherer, s.models.verifier, s.models.max_output_tokens, s.budget.llm_timeout_seconds)
    if search is None:
        search = TavilyClient(base_url=s.tavily.base_url, search_depth=s.tavily.search_depth,
                              extract_depth=s.tavily.extract_depth, timeout_s=s.budget.search_timeout_seconds)
    return llm, search


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def _pipeline(st: _State, company: str, country: str | None, website: str | None) -> None:
    entity = _identity_step(st, company, country, website)
    if entity is None:
        return
    st.entity = entity
    st.result.entity = entity
    if entity.website:
        st.allowlist = st.cfg.allowlist.with_company(entity.website, entity.legal_name)

    plan = _plan_step(st, entity)
    st.result.plan = plan
    st.check_time()

    pages = _search_step(st, [p for p in plan if p.umbrella is not None])
    st.check_time()
    _analyse_pages(st, pages, followup_id=None)
    st.check_time()

    _followup_step(st, entity)
    st.check_time()
    _finalise(st, write_summary=True)


# -- 1. identity -------------------------------------------------------------


def _identity_step(st: _State, company: str, country: str | None, website: str | None) -> ConfirmedEntity | None:
    st.emit("identity", f"Identifying the legal entity for “{company}”.", company=company, country=country, website=website)
    allow = st.cfg.allowlist.with_company(website, company) if website else st.cfg.allowlist
    tiers: list[TierId] = list(st.cfg.settings.identity.tiers)
    if website:
        tiers.append("company_own")
    # The website hint restricts by domain (company_own tier); it is not added to the query text.
    query = " ".join(x for x in (company, "company headquarters legal name", country or "") if x)
    plan_item = PlannedSearch(id="identity-1", umbrella=None, purpose="Identify the legal entity", query=query,
                              tiers=tiers, topic="general", start_date=None)
    st.result.plan.append(plan_item)

    hits = _run_search(st, plan_item, allow)
    blocks: list[str] = []
    urls: dict[str, str] = {}
    for i, (hit, _match) in enumerate(hits[:10], start=1):
        sid = f"I{i}"
        urls[sid] = hit.url
        blocks.append(wrap_untrusted(sid, hit.url, hit.title, hit.content, max_chars=1500))

    candidates = []
    if blocks:
        user = (
            f"Typed company name: {company}\nCountry hint: {country or '(none)'}\nWebsite hint: {website or '(none)'}\n\n"
            + "".join(blocks)
        )
        try:
            out = _bounded(st, st.llm.structured, role="gatherer", system=_system("identity"), user=user, schema=IdentityOutput)
            candidates = out.candidates
        except LLMError as exc:
            st.result.stats.llm_errors += 1
            st.warn(f"Identity model failed: {exc}")

    entity, clarification = resolve_identity(candidates, company, country, website, urls)
    if clarification is not None:
        clarification.candidates = clarification.candidates[: st.cfg.settings.identity.max_candidates_shown]
        st.result.status = "needs_clarification"
        st.result.clarification = clarification
        st.emit("identity", clarification.question, candidates=[c.model_dump() for c in clarification.candidates])
        return None
    assert entity is not None
    st.emit("identity", f"Confirmed: {entity.legal_name} ({entity.country_name or entity.country_code or 'country unknown'}).",
            entity=entity.model_dump())
    return entity


# -- 2. plan -----------------------------------------------------------------


def _start_date(st: _State, lookback: str) -> str:
    rec = st.cfg.settings.recency
    years = rec.legal_years if lookback == "legal" else rec.default_years
    return (st.today - timedelta(days=round(365.25 * years))).isoformat()


def _plan_step(st: _State, entity: ConfirmedEntity) -> list[PlannedSearch]:
    plan: list[PlannedSearch] = list(st.result.plan)  # keeps identity step
    slots: list[PlannedSearch] = []
    country = entity.country_name or entity.country_code or ""
    for umb in UMBRELLAS:
        u = st.cfg.settings.umbrellas[umb]
        for i, tmpl in enumerate(u.searches, start=1):
            tiers: list[TierId] = [t for t in tmpl.tiers if st.allowlist.domains_for([t])]
            draft = tmpl.query.replace("{company}", entity.legal_name).replace("{country}", country).strip()
            if not tiers or (("{country}" in tmpl.query) and not country):
                status: Literal["planned", "skipped"] = "skipped"
            else:
                status = "planned"
            slots.append(PlannedSearch(id=f"{umb}-{i}", umbrella=umb, purpose=f"{u.label}: {', '.join(tiers) or 'no sources'}",
                                       query=draft, tiers=tiers, topic=tmpl.topic, start_date=_start_date(st, tmpl.lookback),
                                       status=status))

    active = [s for s in slots if s.status == "planned"]
    lines = "\n".join(f"- slot_id={s.id} area={s.umbrella} draft={s.query}" for s in active)
    user = (f"Company: {entity.legal_name}\nCountry: {country or 'unknown'}\nWebsite: {entity.website or 'unknown'}\n\n"
            f"Slots:\n{lines}\n")
    try:
        out = _bounded(st, st.llm.structured, role="gatherer", system=_system("plan"), user=user, schema=PlanOutput)
        by_id = {s.id: s for s in active}
        core = _norm_name(entity.legal_name).split(" ")[0] if _norm_name(entity.legal_name) else ""
        for q in out.queries:
            slot = by_id.get(q.slot_id)
            text = " ".join(q.query.split())[:200]
            if slot is None or not text:
                continue
            needs_name = core and core in _norm_name(slot.query)
            if needs_name and core not in _norm_name(text):
                continue  # rewritten query lost the company name; keep the draft
            slot.query = text
    except LLMError as exc:
        st.result.stats.llm_errors += 1
        st.warn(f"Query planner failed, using draft queries: {exc}")

    plan += slots
    st.emit(
        "plan",
        f"Research plan: {len(active)} searches across 6 risk areas, official sources first, then news.",
        steps=[{"id": s.id, "area": s.umbrella, "query": s.query, "tiers": s.tiers, "status": s.status} for s in slots],
        budget=st.cfg.settings.budget.model_dump(),
    )
    return plan


# -- 3. search ---------------------------------------------------------------


def _run_search(st: _State, item: PlannedSearch, allow: Allowlist) -> list[tuple[SearchHit, Any]]:
    """Run one allowlisted search. Returns hits that passed the allowlist, best tier first."""
    if not st.budget.take_search():
        item.status = "skipped"
        if st.budget.timed_out:
            raise _Timeout()
        st.warn(f"Search budget used up; skipped {item.id}.")
        return []
    req = SearchRequest(query=item.query, include_domains=allow.domains_for(item.tiers), topic=item.topic,
                        start_date=item.start_date, max_results=st.cfg.settings.budget.max_results_per_search)
    st.emit("search", f"Searching {item.id}: {item.query}", step=item.id, tiers=item.tiers)
    try:
        hits = _bounded(st, st.search.search, req)
    except SearchError as exc:
        item.status = "failed"
        st.warn(f"Search {item.id} failed: {exc}")
        return []
    kept: list[tuple[SearchHit, Any]] = []
    for h in hits:
        m = allow.match(h.url)
        if m is None or m.tier not in item.tiers:
            item.results_dropped_not_allowlisted += 1
            continue
        kept.append((h, m))
    with st.lock:
        st.result.stats.results_dropped_not_allowlisted += item.results_dropped_not_allowlisted
    kept.sort(key=lambda hm: (allow.priority.get(hm[1].tier, 9), -hm[0].score))
    item.status = "done"
    item.results_kept = len(kept)
    return kept


def _search_step(st: _State, slots: list[PlannedSearch]) -> list[_Page]:
    active = [s for s in slots if s.status == "planned"]
    results: dict[str, list[tuple[SearchHit, Any]]] = {}
    pool = ThreadPoolExecutor(max_workers=st.cfg.settings.budget.parallel_workers)
    try:
        futs = {pool.submit(_run_search, st, s, st.allowlist): s for s in active}
        _collect(st, futs, lambda s, r: results.__setitem__(s.id, r))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)  # never wait past the wall clock

    # Pick pages round-robin across umbrellas so every area gets coverage.
    per_umbrella: dict[str, list[tuple[PlannedSearch, SearchHit, Any]]] = {u: [] for u in UMBRELLAS}
    for s in active:
        for h, m in results.get(s.id, []):
            per_umbrella[cast(str, s.umbrella)].append((s, h, m))
    for u in per_umbrella:
        per_umbrella[u].sort(key=lambda x: (st.allowlist.priority.get(x[2].tier, 9), -x[1].score))
    chosen: list[tuple[PlannedSearch, SearchHit, Any]] = []
    cap = st.cfg.settings.budget.max_pages_per_umbrella
    taken = {u: 0 for u in UMBRELLAS}
    progress = True
    while progress:
        progress = False
        for u in UMBRELLAS:
            while per_umbrella[u] and taken[u] < cap:
                s, h, m = per_umbrella[u].pop(0)
                if h.url in st.seen_urls:
                    continue
                st.seen_urls.add(h.url)
                chosen.append((s, h, m))
                taken[u] += 1
                progress = True
                break
    granted = st.budget.take_extracts(len(chosen), keep_for_followups=True)
    if granted < len(chosen):
        st.emit("extract", f"Page budget: reading {granted} of {len(chosen)} candidate pages.")
    return _fetch_pages(st, chosen[:granted], found_by_override=None)


def _fetch_pages(st: _State, chosen: list[tuple[PlannedSearch, SearchHit, Any]], found_by_override: str | None) -> list[_Page]:
    if not chosen:
        return []
    urls = [h.url for _, h, _ in chosen]
    st.emit("extract", f"Reading {len(urls)} pages from trusted sources.", urls=urls)
    pages_text: dict[str, str] = {}
    try:
        ext = _bounded(st, st.search.extract, urls)
        pages_text = ext.pages
        for u, err in ext.failed.items():
            st.emit("warning", f"Could not read full page, using search snippet: {u}", error=err)
    except SearchError as exc:
        st.warn(f"Page extraction failed, using search snippets: {exc}")
    pages: list[_Page] = []
    for s, h, m in chosen:
        text = pages_text.get(h.url) or ""
        origin: Literal["extract", "search_snippet"] = "extract"
        if not text.strip():
            text, origin = h.content, "search_snippet"
        if not text.strip():
            continue
        src = Source(id=st.new_source_id(), url=h.url, title=h.title or h.url, publisher=m.publisher, tier=m.tier,
                     published_date=h.published_date, retrieved_at=st.now_iso, found_by=found_by_override or s.id,
                     umbrella=s.umbrella, text_origin=origin)
        with st.lock:
            if st.closed:
                break
            st.sources[src.id] = src
            st.result.stats.pages_read += 1
        pages.append(_Page(source=src, text=text))
    return pages


def _collect(st: _State, futs: dict[Future[Any], Any], on_result: Callable[[Any, Any], None]) -> None:
    """Wait for futures until done or the wall clock runs out."""
    pending = set(futs)
    while pending:
        remaining = st.budget.remaining()
        if remaining <= 0:
            for f in pending:
                f.cancel()
            raise _Timeout()
        done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
        for f in done:
            exc = f.exception()
            if isinstance(exc, _Timeout):
                for p in pending:
                    p.cancel()
                raise _Timeout()
            if exc is not None:
                st.warn(f"Step failed: {type(exc).__name__}: {exc}")
                continue
            on_result(futs[f], f.result())


# -- 4. extract + verify ---------------------------------------------------------


def _analyse_pages(st: _State, pages: list[_Page], followup_id: str | None) -> list[Flag]:
    """Analyse pages in parallel, then number and merge flags in page order (deterministic IDs)."""
    if not pages:
        return []
    per_page: dict[str, list[Flag]] = {}
    pool = ThreadPoolExecutor(max_workers=st.cfg.settings.budget.parallel_workers)
    try:
        futs = {pool.submit(_analyse_page, st, p, followup_id): p for p in pages}
        _collect(st, futs, lambda p, flags: per_page.__setitem__(p.source.id, flags))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    ordered: list[Flag] = []
    for p in pages:
        for f in per_page.get(p.source.id, []):
            f.id = st.new_flag_id()
            ordered.append(f)
    return _merge_flags(st, ordered)


def _analyse_page(st: _State, page: _Page, followup_id: str | None) -> list[Flag]:
    assert st.entity is not None
    src = page.source
    area = src.umbrella or "reputation"
    label = st.cfg.settings.umbrellas[area].label
    block = wrap_untrusted(src.id, src.url, src.title, page.text)
    head = (f"Company being researched: {st.entity.legal_name} (country: {st.entity.country_name or st.entity.country_code or 'unknown'}, "
            f"website: {st.entity.website or 'unknown'})\nRisk area searched: {label}\n"
            f"Source: {src.publisher}, published {src.published_date or 'date not stated'}\n\n")
    st.check_time()
    try:
        ext = _bounded(st, st.llm.structured, role="gatherer", system=_system("extract"), user=head + block, schema=ExtractOutput)
    except LLMError as exc:
        with st.lock:
            st.result.stats.llm_errors += 1
        st.warn(f"Fact extraction failed for {src.url}: {exc}")
        return []
    facts = ext.facts[:5]
    with st.lock:
        st.result.stats.candidate_facts += len(facts)

    # Deterministic anti-hallucination check: the quote must be in the text Tavily returned.
    checked: list[tuple[str, CandidateFactOut]] = []
    for i, f in enumerate(facts, start=1):
        if quote_in_text(f.quote, page.text):
            checked.append((f"C{i}", f))
        else:
            _reject(st, src.id, f.claim, "Quote not found in source text")
            with st.lock:
                st.result.stats.rejected_quote_not_found += 1
    if not checked:
        st.emit("verify", f"{src.publisher}: no verifiable facts.", source_id=src.id)
        return []

    payload = [{"fact_id": fid, "claim": f.claim, "quote": f.quote, "entity_named": f.entity_named,
                "event_date": f.event_date} for fid, f in checked]
    user = head + block + "\nCandidate facts (data produced by another model, check each one):\n" + json.dumps(payload, indent=2)
    st.check_time()
    try:
        ver = _bounded(st, st.llm.structured, role="verifier", system=_system("verify"), user=user, schema=VerifyOutput)
    except LLMError as exc:
        with st.lock:
            st.result.stats.llm_errors += 1
        st.warn(f"Verifier failed for {src.url}; its facts were not used: {exc}")
        for _, f in checked:
            _reject(st, src.id, f.claim, "Verifier unavailable")
        return []

    by_id = {v.fact_id: v for v in ver.verdicts}
    flags: list[Flag] = []
    for fid, f in checked:
        v = by_id.get(fid)
        if v is None:
            _reject(st, src.id, f.claim, "Verifier gave no verdict")
            _bump(st, "rejected_by_verifier")
            continue
        if not v.supported:
            _reject(st, src.id, f.claim, v.reject_reason or "Not supported by the source")
            _bump(st, "rejected_by_verifier")
            continue
        if v.entity_match not in ("exact", "group"):
            _reject(st, src.id, f.claim, v.reject_reason or f"Entity {v.entity_match}: {f.entity_named}")
            _bump(st, "rejected_namesake_or_unclear_entity")
            continue
        if not v.relevant:
            _reject(st, src.id, f.claim, v.reject_reason or "Not relevant to supplier risk")
            _bump(st, "rejected_irrelevant")
            continue
        event_date = v.event_date or f.event_date or None
        c = classify(v.event_type, v.severity, event_date, area, st.cfg.rules, st.today, st.cfg.settings.recency.default_years)
        company_stated = src.tier == "company_own"
        flags.append(Flag(
            id="pending", colour=c.colour, area=c.area, event_type=v.event_type, severity=v.severity,
            claim_status=v.claim_status, summary=(v.summary or f.claim).strip(), quote=trim_quote(f.quote),
            event_date=event_date, source_ids=[src.id], company_stated=company_stated, knockout=c.knockout,
            stale=c.stale, rule_note=c.note + ("; company-stated" if company_stated else "") + (f"; entity {v.entity_match}" if v.entity_match == "group" else ""),
            found_in_followup=followup_id is not None,
        ))
        _bump(st, "verified_facts")
    st.emit("verify", f"{src.publisher}: {len(flags)} of {len(facts)} facts verified.", source_id=src.id,
            colours=[fl.colour for fl in flags])
    return flags


def _bump(st: _State, name: str) -> None:
    with st.lock:
        if not st.closed:
            setattr(st.result.stats, name, getattr(st.result.stats, name) + 1)


def _reject(st: _State, source_id: str, claim: str, reason: str) -> None:
    with st.lock:
        if not st.closed:
            st.result.rejected.append(RejectedFact(source_id=source_id, claim=claim, reason=reason))


def _same_event(a: Flag, b: Flag) -> bool:
    return a.event_type == b.event_type and (a.event_date or "")[:7] == (b.event_date or "")[:7] and bool(a.event_date)


def _merge_flags(st: _State, new: list[Flag]) -> list[Flag]:
    """Add flags to the run; a second source for the same event is merged as corroboration."""
    out: list[Flag] = []
    with st.lock:
        if st.closed:
            return out
        for f in new:
            twin = next((g for g in st.flags if _same_event(g, f)), None)
            if twin is not None:
                for sid in f.source_ids:
                    if sid not in twin.source_ids:
                        twin.source_ids.append(sid)
                if twin.company_stated and not f.company_stated:
                    twin.company_stated = False  # independently confirmed
                out.append(twin)
            else:
                st.flags.append(f)
                out.append(f)
    return out


# -- 5. dig deeper -------------------------------------------------------------


def _followup_step(st: _State, entity: ConfirmedEntity) -> None:
    b = st.cfg.settings.budget
    candidates = [f for f in sort_flags(st.flags) if f.colour in ("red", "amber") and not f.stale]
    if not candidates or b.max_followups <= 0:
        st.emit("followup", "No red or watch items to dig into.")
        return
    shown = candidates[:6]
    lines = "\n".join(f"- id={f.id} colour={f.colour} area={f.area} date={f.event_date or 'unknown'} "
                      f"sources={len(f.source_ids)} summary={f.summary}" for f in shown)
    user = (f"Company: {entity.legal_name}\nPick at most {b.max_followups} flags.\n\nVerified flags:\n{lines}\n")
    picks: list[tuple[Flag, str, str]] = []
    valid = {f.id: f for f in shown}
    try:
        out = _bounded(st, st.llm.structured, role="verifier", system=_system("followup"), user=user, schema=FollowupOutput)
        for p in out.picks:
            if p.flag_id in valid and all(p.flag_id != x[0].id for x in picks):
                picks.append((valid[p.flag_id], " ".join(p.question.split())[:200], " ".join(p.query.split())[:150]))
    except LLMError as exc:
        st.result.stats.llm_errors += 1
        st.warn(f"Follow-up picker failed; using rule-based choice: {exc}")
    if not picks:  # deterministic fallback: most serious red flags
        for f in [c for c in candidates if c.colour == "red"][: b.max_followups]:
            picks.append((f, "Is there more recent or corroborating information?", f"{entity.legal_name} {f.summary}"[:150]))

    for n, (flag, question, query) in enumerate(picks[: b.max_followups], start=1):
        st.check_time()
        if not st.budget.take_followup():
            break
        fu = Followup(id=f"followup-{n}", flag_id=flag.id, flag_summary=flag.summary, question=question, query=query)
        st.result.followups.append(fu)
        st.emit("followup", f"Digging deeper on: {flag.summary} — {question}", followup_id=fu.id, flag_id=flag.id, query=query)
        tiers: list[TierId] = [t for t in ("official", "major_news", "rail_trade", "company_own") if st.allowlist.domains_for([t])]
        item = PlannedSearch(id=fu.id, umbrella=flag.area, purpose=f"Follow-up on {flag.id}: {question}", query=query,
                             tiers=tiers, topic="general", start_date=_start_date(st, "legal"))
        st.result.plan.append(item)
        hits = [(h, m) for h, m in _run_search(st, item, st.allowlist) if h.url not in st.seen_urls]
        hits = hits[: b.pages_per_followup]
        granted = st.budget.take_extracts(len(hits), keep_for_followups=False)
        chosen = [(item, h, m) for h, m in hits[:granted]]
        for _, h, _ in chosen:
            st.seen_urls.add(h.url)
        pages = _fetch_pages(st, chosen, found_by_override=fu.id)
        fu.pages_checked = len(pages)
        before = set(flag.source_ids)
        found = _analyse_pages(st, pages, followup_id=fu.id)
        fu.corroborating_source_ids = [s for s in flag.source_ids if s not in before]
        fu.new_flag_ids = sorted({f.id for f in found if f.id != flag.id}, key=lambda x: int(x[1:]))
        fu.outcome = _followup_outcome(st, fu)
        st.emit("followup", f"Follow-up result: {fu.outcome}", followup_id=fu.id)


def _followup_outcome(st: _State, fu: Followup) -> str:
    if fu.pages_checked == 0:
        return "No further trusted source found within the budget."
    parts = []
    if fu.corroborating_source_ids:
        n = len(fu.corroborating_source_ids)
        parts.append("Confirmed by a second source." if n == 1 else f"Confirmed by {n} more sources.")
    by_id = {f.id: f for f in st.flags}
    for fid in fu.new_flag_ids[:2]:
        f = by_id[fid]
        parts.append(f"New: {f.summary}")
    if not parts:
        return f"Checked {plural(fu.pages_checked, 'more page')}; nothing new was verified."
    return " ".join(parts)


# -- 6. finalise -----------------------------------------------------------------


def _finalise(st: _State, write_summary: bool) -> None:
    r = st.result
    rules = st.cfg.rules
    flags = sort_flags(st.flags)
    r.flags = flags
    used_ids = {sid for f in flags for sid in f.source_ids}
    ordered_sources = sorted(st.sources.values(), key=lambda s: int(s.id[1:]))
    r.sources = ordered_sources
    pages_by_area: dict[str, int] = {}
    for s in ordered_sources:
        if s.umbrella:
            pages_by_area[s.umbrella] = pages_by_area.get(s.umbrella, 0) + 1
    labels: dict[str, str] = {u: st.cfg.settings.umbrellas[u].label for u in UMBRELLAS}
    r.areas = area_statuses(flags, pages_by_area, labels)
    r.verdict = overall_verdict(flags, rules, pages_read=r.stats.pages_read)
    r.next_steps = next_steps(flags, rules)
    not_assessed = [a.label for a in r.areas if a.status == "not_assessed"]
    publishers = sorted({s.publisher for s in ordered_sources})
    r.limits = [
        f"Checked {plural(r.stats.pages_read, 'page')} from {plural(len(publishers), 'allowlisted publisher')}; "
        f"{plural(r.stats.results_dropped_not_allowlisted, 'result')} from other sites ignored."
        + (f" Not assessed: {', '.join(not_assessed)}." if not_assessed else ""),
        "Automated public-source research, not independent verification or supplier qualification; "
        f"{plural(len(r.rejected), 'unsupported, off-topic or namesake fact')} discarded.",
        "Not linked to the anonymized SUPP_* records in the challenge dataset.",
    ]
    if r.status == "partial":
        r.limits[0] += " The run hit its time limit, so coverage is incomplete."
    if write_summary and flags:
        r.summary = _write_summary(st, flags)
    if not r.summary:
        r.summary = _fallback_summary(r.verdict, flags, r.stats.pages_read, not_assessed)
    st.emit("report", "Report ready.", verdict=r.verdict, flags=len(flags), cited_sources=len(used_ids))


def _write_summary(st: _State, flags: list[Flag]) -> str:
    assert st.entity is not None
    facts = [{"colour": f.colour, "area": f.area, "status": f.claim_status, "date": f.event_date,
              "company_stated": f.company_stated, "finding": f.summary} for f in flags if f.colour != "neutral"][:15]
    not_assessed = [a.label for a in st.result.areas if a.status == "not_assessed"]
    user = (f"Company: {st.entity.legal_name}\nVerdict (decided by rules): {st.result.verdict}\n"
            f"Areas not assessed: {', '.join(not_assessed) or 'none'}\n"
            f"Verified findings (the only facts you may use):\n{json.dumps(facts, indent=2)}\n")
    try:
        out = _bounded(st, st.llm.structured, role="verifier", system=_system("summary"), user=user, schema=SummaryOutput)
    except LLMError as exc:
        st.result.stats.llm_errors += 1
        st.warn(f"Summary writer failed; using template summary: {exc}")
        return ""
    text = " ".join(out.summary.split())
    if re.search(r"\bno risks?\b", text, re.IGNORECASE):
        return ""  # never claim "no risk"
    return text[:700]


def _fallback_summary(verdict: str, flags: list[Flag], pages: int, not_assessed: list[str]) -> str:
    n = {c: sum(1 for f in flags if f.colour == c) for c in ("red", "amber", "green")}
    text = (f"{verdict}. Found {plural(n['red'], 'red flag')}, {plural(n['amber'], 'watch item')} and "
            f"{plural(n['green'], 'strength')} in {plural(pages, 'trusted source')}.")
    if not_assessed:
        text += f" Not assessed: {', '.join(not_assessed)}."
    return text


_R = TypeVar("_R")


def _bounded(st: _State, fn: Callable[..., _R], *args: Any, **kwargs: Any) -> _R:
    """Run a blocking network/model call, but never wait past the run's wall clock.

    The call runs in a daemon thread; on timeout it is abandoned (its result is ignored)
    and the pipeline returns partial results.
    """
    remaining = st.budget.remaining()
    if remaining <= 0:
        raise _Timeout()
    box: dict[str, Any] = {}
    done = threading.Event()

    def target() -> None:
        try:
            box["value"] = fn(*args, **kwargs)
        except BaseException as exc:  # re-raised in the caller's thread
            box["error"] = exc
        finally:
            done.set()

    threading.Thread(target=target, daemon=True).start()
    if not done.wait(remaining):
        raise _Timeout()
    if "error" in box:
        raise box["error"]
    return cast(_R, box["value"])


def _system(prompt_name: str) -> str:
    return load_prompt(prompt_name).strip() + "\n\n" + UNTRUSTED_NOTICE
