"""The research pipeline: identity → plan → search → extract → verify → rules → dig deeper → report.

Entry point for the chatbot/UI: :func:`run_research`.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, TypeVar, cast

from .budget import Budget, split_by_weight
from .dates import month_key, normalize_date, parse_date
from .cache import CachingLLM, CachingSearch, DayCache
from .country_data import CachedCPI, CountryDataSource, CountryFigure, DirectWGI, TavilyWGI, band_for
from .config import CONFIG_DIR, PROMPTS_DIR, TIER_IDS, AgentConfig, Allowlist, ConfigError, SourceMatch, domain_of, load_all, load_prompt
from .identity import _COUNTRY_NAMES, _norm_name, resolve_identity
from .llm import LLM, AnthropicLLM, LLMError
from .models import (
    UMBRELLAS,
    DroppedResult,
    DropReason,
    CandidateFactOut,
    ConfirmedEntity,
    ExtractOutput,
    Flag,
    Followup,
    FollowupOutput,
    GradingSignals,
    IdentityOutput,
    NumericFact,
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
from .numeric_facts import accept_pages, build_inputs, check_number, source_reliability
from .scoring import score_detailed, score_result
from .search import SearchClient, SearchError, SearchHit, SearchRequest, TavilyClient
from .untrusted import UNTRUSTED_NOTICE, wrap_untrusted
from .verification import COPY_PASSAGE_WORDS, independent_groups, quote_context, quote_in_text, shingles, trim_quote

ProgressCallback = Callable[[ProgressEvent], None]
PKG_DIR = Path(__file__).parent


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
    page_shingles: dict[str, frozenset[str]] = field(default_factory=dict)  # source id -> text fingerprint
    page_texts: dict[str, str] = field(default_factory=dict)  # source id -> text read (copy test, numbers, grades)
    numbers: list[NumericFact] = field(default_factory=list)
    contradicted: set[str] = field(default_factory=set)  # flag ids a trusted page contradicted
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
    cache: DayCache | None = None,
    page_texts_out: dict[str, str] | None = None,
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

    built_llm, built_search = llm is None, search is None
    if llm is None or search is None:
        try:
            llm, search = build_live_clients(cfg, llm, search)
        except (LLMError, SearchError) as exc:
            result.status = "error"
            result.warnings.append(str(exc))
            return result
    # Same-day cache: always for the live clients built here (when enabled); for injected
    # clients (tests, fixture demo) only when a cache is passed in explicitly.
    explicit = cache is not None
    if cache is None and (built_llm or built_search) and cfg.settings.cache.enabled:
        cache = DayCache(PKG_DIR / cfg.settings.cache.dir, today.isoformat())
    if cache is not None:
        m = cfg.settings.models
        if built_llm or explicit:
            llm = CachingLLM(llm, cache, settings_key=f"{m.gatherer_effort}/{m.verifier_effort}/{m.max_output_tokens}")
        if built_search or explicit:
            search = CachingSearch(search, cache)

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
    result.stats.cache_hits = cache.hits if cache is not None else 0
    result.fingerprint = run_fingerprint(cfg, result, cache_day=cache.dir.name if cache is not None else None)
    if page_texts_out is not None:  # for report.html citation context; not stored in result.json
        page_texts_out.update(st.page_texts)
    st.emit("done", f"Research finished with status '{result.status}'.", status=result.status)
    return result


def run_fingerprint(cfg: AgentConfig, result: ResearchResult, cache_day: str | None) -> dict[str, Any]:
    """What a run depended on, so two runs can be diffed: config and prompt hash, models and
    effort, cache day, country-data source, and the exact queries."""
    h = hashlib.sha256()
    for path in sorted([*CONFIG_DIR.glob("*.yaml"), *PROMPTS_DIR.glob("*.md")]):
        h.update(path.name.encode())
        h.update(path.read_bytes())
    m = cfg.settings.models
    return {
        "config_hash": h.hexdigest()[:16],
        "models": dict(result.models),
        "effort": {"gatherer": m.gatherer_effort, "verifier": m.verifier_effort},
        "cache_day": cache_day,
        "country_data": cfg.settings.country_data.wgi_source,
        "queries": [{"id": p.id, "lang": p.lang, "status": p.status, "query": p.query} for p in result.plan],
    }


def build_live_clients(cfg: AgentConfig, llm: LLM | None = None, search: SearchClient | None = None) -> tuple[LLM, SearchClient]:
    """Create the real Claude + Tavily clients from environment variables."""
    s = cfg.settings
    if llm is None:
        llm = AnthropicLLM(s.models.gatherer, s.models.verifier, s.models.max_output_tokens, s.budget.llm_timeout_seconds,
                           gatherer_effort=s.models.gatherer_effort, verifier_effort=s.models.verifier_effort)
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
    _country_step(st, entity)
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


def _country_slug(entity: ConfirmedEntity) -> str:
    name = entity.country_name or _COUNTRY_NAMES.get(entity.country_code.upper(), "")
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _english_speaking(st: _State, entity: ConfirmedEntity) -> bool:
    return entity.country_code.upper() in {c.upper() for c in st.cfg.settings.english_speaking_countries}


def _extra_words(query: str, entity: ConfirmedEntity) -> int:
    """Words in a query besides the company's name (legal suffixes count as part of the name)."""
    name = set(entity.legal_name.lower().split()) | set(_norm_name(entity.legal_name).split())
    return len([w for w in query.split() if w.lower().strip(",.;:") not in name])


def _plan_step(st: _State, entity: ConfirmedEntity) -> list[PlannedSearch]:
    """Queries come from the templates: English as written, local language from the fixed
    translation for the country's language. Only local slots without a translation go to the
    planner model (its answer is cached for the day). Same company -> same queries."""
    plan: list[PlannedSearch] = list(st.result.plan)  # keeps identity step
    slots: list[PlannedSearch] = []
    country = entity.country_name or entity.country_code or ""
    english = _english_speaking(st, entity)
    lang_code = st.cfg.settings.country_languages.get(entity.country_code.upper(), "")
    untranslated: list[PlannedSearch] = []
    for umb in UMBRELLAS:
        u = st.cfg.settings.umbrellas[umb]
        for i, tmpl in enumerate(u.searches, start=1):
            tiers: list[TierId] = [t for t in tmpl.tiers if st.allowlist.domains_for([t])]
            fixed = tmpl.local.get(lang_code) if tmpl.lang == "local" else tmpl.query
            text = (fixed or tmpl.query).replace("{company}", entity.legal_name).replace("{country}", country).strip()
            skip = not tiers or (("{country}" in tmpl.query) and not country) or (tmpl.lang == "local" and english)
            status: Literal["planned", "skipped"] = "skipped" if skip else "planned"
            slot = PlannedSearch(id=f"{umb}-{i}", umbrella=umb, purpose=f"{u.label}: {', '.join(tiers) or 'no sources'}"
                                 + (" (local language)" if tmpl.lang == "local" else ""),
                                 query=text, tiers=tiers, topic=tmpl.topic, start_date=_start_date(st, tmpl.lookback),
                                 lang=tmpl.lang, status=status)
            slots.append(slot)
            if status == "planned" and tmpl.lang == "local" and not fixed:
                untranslated.append(slot)

    if untranslated:
        _translate_slots(st, entity, country, untranslated)
    active = [s for s in slots if s.status == "planned"]
    plan += slots
    st.emit(
        "plan",
        f"Research plan: {len(active)} searches across 6 risk areas, official sources first, then news; "
        "open web only to fill gaps.",
        steps=[{"id": s.id, "area": s.umbrella, "query": s.query, "tiers": s.tiers, "lang": s.lang, "status": s.status}
               for s in slots],
        budget=st.cfg.settings.budget.model_dump(),
    )
    return plan


def _translate_slots(st: _State, entity: ConfirmedEntity, country: str, slots: list[PlannedSearch]) -> None:
    """Planner model writes local-language queries where no fixed translation exists."""
    lines = "\n".join(f"- slot_id={s.id} area={s.umbrella} lang=local draft={s.query}" for s in slots)
    user = (f"Company: {entity.legal_name}\nCountry: {country or 'unknown'}\nWebsite: {entity.website or 'unknown'}\n"
            f"lang=local means: write the query in the main language of {country or 'the company country'}.\n"
            f"Maximum query length: the company name plus {st.cfg.settings.max_query_extra_words} words.\n\n"
            f"Slots:\n{lines}\n")
    try:
        out = _bounded(st, st.llm.structured, role="gatherer", system=_system("plan"), user=user, schema=PlanOutput)
    except LLMError as exc:
        st.result.stats.llm_errors += 1
        st.warn(f"Query translation failed, using English drafts: {exc}")
        return
    by_id = {s.id: s for s in slots}
    core = _norm_name(entity.legal_name).split(" ")[0] if _norm_name(entity.legal_name) else ""
    for q in out.queries:
        slot = by_id.get(q.slot_id)
        text = " ".join(q.query.split())[:200]
        if slot is None or not text:
            continue
        if core and core not in _norm_name(text):
            continue  # rewritten query lost the company name; keep the draft
        if _extra_words(text, entity) > st.cfg.settings.max_query_extra_words:
            continue  # keyword soup recalls badly; keep the short draft
        slot.query = text


# -- 2b. country data -------------------------------------------------------------


def _country_step(st: _State, entity: ConfirmedEntity) -> None:
    """Country figures (WGI, CPI) as one structured fact, read by code: no model, no search."""
    cd = st.cfg.settings.country_data
    iso2 = entity.country_code.upper()
    if not iso2:
        st.warn("Country data skipped: country code unknown.")
        return
    name = entity.country_name or _COUNTRY_NAMES.get(iso2, iso2).title()
    providers: list[tuple[str, CountryDataSource]] = []
    if cd.wgi_source == "tavily" and st.budget.take_extracts(1, keep_for_followups=True,
                                                             keep_back=st.cfg.settings.open_web.max_pages):
        providers.append(("World Bank WGI (via Tavily extract)", TavilyWGI(st.search, cd.wgi_indicators)))
    elif cd.wgi_source == "worldbank_api":
        providers.append(("World Bank WGI (direct API)", DirectWGI(cd.wgi_indicators, st.cfg.settings.budget.search_timeout_seconds)))
    if cd.cpi_file:
        providers.append(("TI CPI (official file)", CachedCPI(PKG_DIR / cd.cpi_file, cd.cpi_year, cd.cpi_url)))
    st.emit("extract", f"Reading country data for {name}: {', '.join(p for p, _ in providers) or 'none configured'}.")
    figures: list[CountryFigure] = []
    sids: list[str] = []
    for label, provider in providers:
        try:
            res = _bounded(st, provider.fetch, iso2, name)
        except (SearchError, OSError, ValueError, KeyError) as exc:
            st.warn(f"Country data from {label} failed: {type(exc).__name__}: {exc}")
            continue
        for w in res.warnings:
            st.warn(w)
        for url, text in res.texts.items():
            figs = [f for f in res.figures if f.source_url == url and quote_in_text(f.quote, text)]
            if not figs:
                continue
            src = Source(id=st.new_source_id(), url=url, title=res.titles.get(url, url), publisher=figs[0].publisher,
                         tier="country_data", trust="trusted",
                         published_date=normalize_date(res.published.get(url)) or (cd.cpi_published if figs[0].indicator == "CPI" else None),
                         retrieved_at=st.now_iso, found_by="country-data", umbrella="country", text_origin="data")
            with st.lock:
                st.sources[src.id] = src
                st.page_shingles[src.id] = shingles(text)
                st.page_texts[src.id] = text
                st.result.stats.pages_read += 1
                st.result.stats.trusted_pages_read += 1
            sids.append(src.id)
            figures.extend(figs)
    if not figures:
        return
    st.result.plan.append(PlannedSearch(id="country-data", umbrella="country", purpose="Country & Location: index data",
                                        query=", ".join(sorted({f.indicator for f in figures})), tiers=["country_data"],
                                        topic="general", start_date=None, status="done", results_kept=len(figures)))
    bands = [band_for(f.value, cd.elevated_below, cd.low_at_or_above) for f in figures]
    if "elevated" in bands:
        event, word = "country_risk_elevated", "elevated country risk"
    elif all(b == "low" for b in bands):
        event, word = "country_risk_low", "low country risk"
    else:
        event, word = "other_neutral", "middling country risk"
    parts = []
    for f in figures:
        rank = f" (rank {f.rank} of {f.of})" if f.rank and f.of else ""
        parts.append(f"{f.label.split(' (')[0]} {f.value:.0f}/100{rank}")
    years = sorted({f.year for f in figures})
    summary = f"{name}: {word} in official indices — " + "; ".join(parts) + f" ({'–'.join(str(y) for y in (years[0], years[-1]) if y) if len(years) > 1 else years[0]})."
    c = classify(event, "medium" if event == "country_risk_elevated" else "low", str(max(years)), "country", st.cfg.rules,
                 st.today, st.cfg.settings.recency.default_years)
    flag = Flag(id=st.new_flag_id(), colour=c.colour, area="country", event_type=cast(Any, event),
                severity="medium" if event == "country_risk_elevated" else "low", claim_status="confirmed",
                summary=summary, quote=trim_quote(figures[0].quote), event_date=str(max(years)), source_ids=sids,
                stale=c.stale, rule_note=c.note + f"; bands on 0-100: < {cd.elevated_below} elevated, "
                f">= {cd.low_at_or_above} low; worst indicator decides",
                signals=GradingSignals(publisher_named=True, dated=True, claim_specific_checkable=True,
                                       cites_primary_document=True, attribution="firsthand_official"),
                data={"figures": [{"indicator": f.indicator, "label": f.label, "value": f.value, "year": f.year,
                                   "scale": f.scale, "rank": f.rank, "of": f.of, "source_url": f.source_url,
                                   "quote": f.quote}
                                  for f in figures],
                      "band": dict(zip([f.indicator for f in figures], bands, strict=True))})
    with st.lock:
        st.flags.append(flag)
        st.result.stats.verified_facts += 1
    st.emit("verify", f"Country data: {summary}", colours=[flag.colour])


# -- 3. search ---------------------------------------------------------------


def _drop(st: _State, item: PlannedSearch, hit: SearchHit, reason: DropReason) -> None:
    """Record why a result was not read: per search (result.plan[].dropped) and per reason (stats)."""
    with st.lock:
        if st.closed:
            return
        item.dropped.append(DroppedResult(url=hit.url, title=hit.title[:200], reason=reason))
        st.result.stats.drop_reasons[reason] = st.result.stats.drop_reasons.get(reason, 0) + 1


def _hit_key(st: _State, umbrella: str | None, hit: SearchHit, m: SourceMatch) -> tuple[int, int, float, str]:
    """Stable order: tier, then (areas with prefer_recent) newest first, then score, then URL.
    The URL breaks ties so the same results always come out in the same order."""
    recent = 0
    if umbrella and st.cfg.settings.umbrellas[umbrella].prefer_recent:
        d = parse_date(hit.published_date)
        recent = -(d.toordinal() if d else 0)
    return (st.allowlist.rank(m), recent, -round(hit.score, 4), hit.url)


def _run_search(st: _State, item: PlannedSearch, allow: Allowlist) -> list[tuple[SearchHit, SourceMatch]]:
    """Run one search. Returns usable hits, in a stable order.

    Trusted searches (``item.open_web`` False) keep only allowlisted hits from the requested
    tiers. Open-web searches exclude the allowlist and the denylist and keep the rest as
    unverified. Denylisted hits are always dropped. Every dropped hit is recorded with a reason."""
    if not st.budget.take_search():
        item.status = "skipped"
        if st.budget.timed_out:
            raise _Timeout()
        st.warn(f"Search budget used up; skipped {item.id}.")
        return []
    if item.open_web:
        # Trusted domains were already searched with the same query, so they are excluded too.
        excluded = allow.denied_domains() + allow.domains_for(list(TIER_IDS))
        req = SearchRequest(query=item.query, include_domains=[], topic=item.topic, start_date=item.start_date,
                            max_results=st.cfg.settings.budget.max_results_per_search, open_web=True,
                            exclude_domains=excluded)
        st.emit("search", f"Searching the open web for {item.id}: {item.query}", step=item.id, open_web=True)
    else:
        req = SearchRequest(query=item.query, include_domains=allow.domains_for(item.tiers), topic=item.topic,
                            start_date=item.start_date, max_results=st.cfg.settings.budget.max_results_per_search)
        st.emit("search", f"Searching {item.id}: {item.query}", step=item.id, tiers=item.tiers)
    try:
        hits = _bounded(st, st.search.search, req)
    except SearchError as exc:
        item.status = "failed"
        st.warn(f"Search {item.id} failed: {exc}")
        return []
    kept: list[tuple[SearchHit, SourceMatch]] = []
    for h in hits:
        m = allow.classify(h.url)
        if m is None:
            item.results_dropped_denylisted += 1
            _drop(st, item, h, "denylisted")
            continue
        if item.open_web and m.trust == "trusted":
            _drop(st, item, h, "trusted_site_in_open_web")
            continue
        if not item.open_web and (m.trust != "trusted" or m.tier not in item.tiers):
            item.results_dropped_not_allowlisted += 1
            _drop(st, item, h, "not_allowlisted")
            continue
        if m.tier in _NAME_CHECK_TIERS and st.entity is not None and not _mentions_company(st.entity, h):
            item.results_dropped_off_topic += 1
            _drop(st, item, h, "off_topic")
            continue
        kept.append((h, m))
    with st.lock:
        st.result.stats.results_dropped_not_allowlisted += item.results_dropped_not_allowlisted
        st.result.stats.results_dropped_denylisted += item.results_dropped_denylisted
        st.result.stats.results_dropped_off_topic += item.results_dropped_off_topic
    kept.sort(key=lambda hm: _hit_key(st, item.umbrella, hm[0], hm[1]))
    item.status = "done"
    item.results_kept = len(kept)
    return kept


_Cand = tuple[PlannedSearch, SearchHit, SourceMatch]

# News and open-web results must name the company in their title or snippet before we spend a
# page extract on them (first live run: two Reuters pages about another company, and an
# unrelated PDF). Registers, the company's own site and country data are exempt: a register
# entry or country page need not repeat the name in the snippet.
_NAME_CHECK_TIERS = ("major_news", "rail_trade", "open_web")
# First words too common to identify a company alone; then the first two words must appear.
_GENERIC_FIRST_WORDS = {"deutsche", "general", "national", "international", "united", "american", "british",
                        "european", "global", "first", "china", "new", "the", "royal", "standard"}


def _name_keys(entity: ConfirmedEntity) -> list[str]:
    """Normalized phrases, any of which counts as 'names the company'."""
    keys: list[str] = []
    words = _norm_name(entity.legal_name).split()
    if words:
        n = 2 if (words[0] in _GENERIC_FIRST_WORDS or len(words[0]) < 4) and len(words) > 1 else 1
        keys.append(" ".join(words[:n]))
    stem = domain_of(entity.website).split(".")[0] if entity.website else ""
    stem_words = _norm_name(stem).split()
    if stem_words and len(" ".join(stem_words)) >= 4:
        keys.append(" ".join(stem_words))
    return keys


def _mentions_company(entity: ConfirmedEntity, hit: SearchHit) -> bool:
    """Title, snippet or URL names the company. Hyphens, spaces and case don't matter
    ("Knorr-Bremse", "Knorr Bremse", "KnorrBremse", ".../knorr-bremse-..." all match). The URL
    counts because news URLs carry the headline even when the snippet is about something else."""
    norm = _norm_name(f"{hit.title} {hit.content} {hit.url.replace('/', ' ').replace('-', ' ').replace('_', ' ')}")
    text, compact = f" {norm} ", norm.replace(" ", "")
    return any(f" {k} " in text or (len(k.replace(' ', '')) >= 6 and k.replace(" ", "") in compact)
               for k in _name_keys(entity))


def _parallel_search(st: _State, items: list[PlannedSearch]) -> dict[str, list[tuple[SearchHit, SourceMatch]]]:
    results: dict[str, list[tuple[SearchHit, SourceMatch]]] = {}
    if not items:
        return results
    pool = ThreadPoolExecutor(max_workers=st.cfg.settings.budget.parallel_workers)
    try:
        futs = {pool.submit(_run_search, st, s, st.allowlist): s for s in items}
        _collect(st, futs, lambda s, r: results.__setitem__(s.id, r))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)  # never wait past the wall clock
    return results


def _round_robin(st: _State, per_umbrella: Mapping[str, list[_Cand]], cap: Mapping[str, int],
                 order: list[str] | None = None) -> list[_Cand]:
    """Pick pages one area at a time so every area gets coverage; skips URLs already chosen."""
    chosen: list[_Cand] = []
    taken: dict[str, int] = {u: 0 for u in UMBRELLAS}
    progress = True
    while progress:
        progress = False
        for u in order or list(UMBRELLAS):
            while per_umbrella.get(u) and taken[u] < cap.get(u, 0):
                s, h, m = per_umbrella[u].pop(0)
                if h.url in st.seen_urls:
                    _drop(st, s, h, "duplicate")
                    continue
                st.seen_urls.add(h.url)
                chosen.append((s, h, m))
                taken[u] += 1
                progress = True
                break
    return chosen


def _drop_rest(st: _State, per_umbrella: Mapping[str, list[_Cand]], reason: DropReason) -> None:
    for cands in per_umbrella.values():
        for s, h, _ in cands:
            _drop(st, s, h, "duplicate" if h.url in st.seen_urls else reason)
        cands.clear()


def _drop_cut(st: _State, cut: list[_Cand], reason: DropReason) -> None:
    for s, h, _ in cut:
        st.seen_urls.discard(h.url)
        _drop(st, s, h, reason)


def _area_shares(st: _State) -> dict[str, int]:
    """Trusted pages per area, split by the area weights in config/scoring.yaml."""
    weights: dict[str, float] = {a: m.weight for a, m in st.cfg.scoring.areas.items()} if st.cfg.scoring else {}
    return split_by_weight(st.cfg.settings.budget.max_trusted_pages, weights, list(UMBRELLAS))


def _weight_order(st: _State) -> list[str]:
    w: dict[str, float] = {a: m.weight for a, m in st.cfg.scoring.areas.items()} if st.cfg.scoring else {}
    return sorted(UMBRELLAS, key=lambda u: (-w.get(u, 0.0), UMBRELLAS.index(u)))


def _search_step(st: _State, slots: list[PlannedSearch]) -> list[_Page]:
    ow = st.cfg.settings.open_web
    active = [s for s in slots if s.status == "planned"]
    results = _parallel_search(st, active)
    shares = _area_shares(st)

    # 1. Trusted pages first, one area at a time, each area up to its weighted share.
    #    Results are taken in plan order and stable hit order, so the same results always
    #    lead to the same pages.
    per_umbrella: dict[str, list[_Cand]] = {u: [] for u in UMBRELLAS}
    for s in active:
        for h, m in results.get(s.id, []):
            per_umbrella[cast(str, s.umbrella)].append((s, h, m))
    for u in per_umbrella:
        per_umbrella[u].sort(key=lambda x: _hit_key(st, u, x[1], x[2]))
    trusted_found: dict[str, int] = {u: len({h.url for _, h, _ in per_umbrella[u]}) for u in UMBRELLAS}
    chosen = _round_robin(st, per_umbrella, shares)
    # 2. Pages an area could not use go to the other areas, highest weight first.
    spare = st.cfg.settings.budget.max_trusted_pages - len(chosen)
    if spare > 0:
        extra_cap: dict[str, int] = {u: spare for u in UMBRELLAS}
        extra = _round_robin(st, per_umbrella, extra_cap, order=_weight_order(st))
        _drop_cut(st, extra[spare:], "page_budget")
        chosen += extra[:spare]
    _drop_rest(st, per_umbrella, "area_cap")
    ow_reserve = ow.max_pages if ow.enabled else 0
    granted = st.budget.take_extracts(len(chosen), keep_for_followups=True, keep_back=ow_reserve)
    if granted < len(chosen):
        st.emit("extract", f"Page budget: reading {granted} of {len(chosen)} candidate trusted pages.")
        _drop_cut(st, chosen[granted:], "page_budget")
    chosen = chosen[:granted]

    # 3. Open web fills gaps: areas whose trusted searches found fewer pages than their share.
    if ow.enabled and ow.max_searches > 0 and ow.max_pages > 0:
        chosen += _open_web_step(st, slots, trusted_found, shares)
    return _fetch_pages(st, chosen, found_by_override=None)


def _open_web_step(st: _State, slots: list[PlannedSearch], trusted_found: Mapping[str, int],
                   shares: Mapping[str, int]) -> list[_Cand]:
    ow = st.cfg.settings.open_web
    order = {u: i for i, u in enumerate(ow.umbrellas)}
    gaps = [u for u in ow.umbrellas if trusted_found.get(u, 0) < shares.get(u, 0)]
    # Areas with no trusted page at all first, then the biggest shortfall against the share.
    gaps.sort(key=lambda u: (trusted_found.get(u, 0) > 0, trusted_found.get(u, 0) - shares.get(u, 0), order[u]))
    items: list[PlannedSearch] = []
    for u in gaps[: ow.max_searches]:
        base = next((s for s in slots if s.umbrella == u and s.lang == "en" and s.status in ("planned", "done")), None)
        if base is None:
            continue
        items.append(PlannedSearch(
            id=f"{u}-web", umbrella=u, purpose=f"{st.cfg.settings.umbrellas[u].label}: open web (gap fill, "
            f"{plural(trusted_found.get(u, 0), 'trusted page')} found)", query=base.query, tiers=[], topic=base.topic,
            start_date=base.start_date, open_web=True))
    if not items:
        return []
    st.result.plan.extend(items)
    st.emit("plan", f"Open web: filling gaps in {', '.join(st.cfg.settings.umbrellas[cast(str, i.umbrella)].label for i in items)}.",
            steps=[{"id": i.id, "area": i.umbrella, "query": i.query, "open_web": True} for i in items])
    results = _parallel_search(st, items)
    per_umbrella: dict[str, list[_Cand]] = {u: [] for u in UMBRELLAS}
    for it in items:
        for h, m in results.get(it.id, []):
            per_umbrella[cast(str, it.umbrella)].append((it, h, m))
    cap: dict[str, int] = {u: ow.max_pages_per_umbrella for u in UMBRELLAS}
    picked = _round_robin(st, per_umbrella, cap)
    _drop_rest(st, per_umbrella, "area_cap")
    _drop_cut(st, picked[ow.max_pages:], "page_budget")
    picked = picked[: ow.max_pages]
    granted = st.budget.take_extracts(len(picked), keep_for_followups=True)
    _drop_cut(st, picked[granted:], "page_budget")
    return picked[:granted]


def _fetch_pages(st: _State, chosen: list[_Cand], found_by_override: str | None) -> list[_Page]:
    if not chosen:
        return []
    urls = [h.url for _, h, _ in chosen]
    n_unv = sum(1 for _, _, m in chosen if m.trust == "unverified")
    extra = f" ({n_unv} from unverified sites)" if n_unv else ""
    st.emit("extract", f"Reading {plural(len(urls), 'page')}{extra}.", urls=urls)
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
            _drop(st, s, h, "extract_failed")
            continue
        src = Source(id=st.new_source_id(), url=h.url, title=h.title or h.url, publisher=m.publisher, tier=m.tier,
                     trust=m.trust, published_date=normalize_date(h.published_date), retrieved_at=st.now_iso,
                     found_by=found_by_override or s.id, umbrella=s.umbrella, text_origin=origin)
        with st.lock:
            if st.closed:
                break
            st.sources[src.id] = src
            st.page_shingles[src.id] = shingles(text)
            st.page_texts[src.id] = text
            st.result.stats.pages_read += 1
            if src.trust == "trusted":
                st.result.stats.trusted_pages_read += 1
            else:
                st.result.stats.unverified_pages_read += 1
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


def _analyse_pages(st: _State, pages: list[_Page], followup_id: str | None,
                   claim_under_check: tuple[str, str] | None = None) -> list[Flag]:
    """Analyse pages in parallel, then number and merge flags in page order (deterministic IDs)."""
    if not pages:
        return []
    per_page: dict[str, list[Flag]] = {}
    pool = ThreadPoolExecutor(max_workers=st.cfg.settings.budget.parallel_workers)
    try:
        futs = {pool.submit(_analyse_page, st, p, followup_id, claim_under_check): p for p in pages}
        _collect(st, futs, lambda p, flags: per_page.__setitem__(p.source.id, flags))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    ordered: list[Flag] = []
    for p in pages:
        for f in per_page.get(p.source.id, []):
            f.id = st.new_flag_id()
            ordered.append(f)
    return _merge_flags(st, ordered)


def _analyse_page(st: _State, page: _Page, followup_id: str | None,
                  claim_under_check: tuple[str, str] | None = None) -> list[Flag]:
    """``claim_under_check`` = (flag id, claim): an unverified flag a trusted follow-up page may contradict."""
    assert st.entity is not None
    src = page.source
    area = src.umbrella or "reputation"
    label = st.cfg.settings.umbrellas[area].label
    block = wrap_untrusted(src.id, src.url, src.title, page.text)
    head = (f"Company being researched: {st.entity.legal_name} (country: {st.entity.country_name or st.entity.country_code or 'unknown'}, "
            f"website: {st.entity.website or 'unknown'})\nRisk area searched: {label}\n"
            f"Source: {src.publisher}, published {src.published_date or 'date not stated'}\n"
            + ("Source trust: UNVERIFIED (this site is not in our trusted source list)\n" if src.trust == "unverified" else "")
            + "\n")
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
    # Numbers for scoring: same quote check, and the value must be inside the quote.
    nums = [check_number(n, page.text, src) for n in ext.numbers[:20]]
    with st.lock:
        if not st.closed:
            st.numbers.extend(nums)

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
    check_contradiction = claim_under_check is not None and src.trust == "trusted"
    if check_contradiction:
        assert claim_under_check is not None
        user += f"\n\nClaim under check (from a site outside our trusted list): {claim_under_check[1]}\n"
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

    if check_contradiction and ver.contradicts_claim_under_check:
        assert claim_under_check is not None
        with st.lock:
            st.contradicted.add(claim_under_check[0])
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
        event_date = normalize_date(v.event_date) or normalize_date(f.event_date)
        trusted = src.trust == "trusted"
        c = classify(v.event_type, v.severity, event_date, area, st.cfg.rules, st.today, st.cfg.settings.recency.default_years,
                     trusted=trusted)
        company_stated = src.tier == "company_own"
        flags.append(Flag(
            id="pending", colour=c.colour, area=c.area, event_type=v.event_type, severity=v.severity,
            claim_status=v.claim_status, summary=(v.summary or f.claim).strip(), quote=trim_quote(f.quote),
            event_date=event_date, source_ids=[src.id], company_stated=company_stated, trust=src.trust,
            quote_context=quote_context(f.quote, page.text),
            capped_unverified=c.capped_unverified, knockout=c.knockout,
            stale=c.stale, rule_note=c.note + ("; company-stated" if company_stated else "") + (f"; entity {v.entity_match}" if v.entity_match == "group" else ""),
            found_in_followup=followup_id is not None,
            signals=GradingSignals(publisher_named=v.publisher_named, dated=v.dated,
                                   claim_specific_checkable=v.claim_specific_checkable,
                                   cites_primary_document=v.cites_primary_document, attribution=v.attribution),
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
    ka, kb = month_key(a.event_date), month_key(b.event_date)
    return a.event_type == b.event_type and ka is not None and ka == kb


def _merge_flags(st: _State, new: list[Flag]) -> list[Flag]:
    """Add flags to the run; a second source for the same event is merged as corroboration."""
    out: list[Flag] = []
    with st.lock:
        if st.closed:
            return out
        for f in new:
            twin = next((g for g in st.flags if _same_event(g, f)), None)
            if twin is not None:
                if twin.trust == "unverified" and f.trust == "trusted":
                    _upgrade_to_trusted(st, twin, f)
                for sid in f.source_ids:
                    if sid not in twin.source_ids:
                        twin.source_ids.append(sid)
                if twin.company_stated and not f.company_stated and f.trust == "trusted":
                    twin.company_stated = False  # independently confirmed
                out.append(twin)
            else:
                st.flags.append(f)
                out.append(f)
    return out


def _upgrade_to_trusted(st: _State, flag: Flag, trusted: Flag) -> None:
    """A trusted source confirms an unverified-only fact: re-rate it without the unverified cap.
    The trusted source is cited first and its quote is shown. Caller holds the lock."""
    before = flag.colour
    c = classify(flag.event_type, flag.severity, flag.event_date, flag.area, st.cfg.rules, st.today,
                 st.cfg.settings.recency.default_years, trusted=True)
    flag.colour, flag.knockout, flag.stale = c.colour, c.knockout, c.stale
    flag.trust, flag.capped_unverified = "trusted", False
    flag.company_stated = trusted.company_stated
    flag.quote = trusted.quote
    flag.signals = trusted.signals.model_copy()  # signals follow the primary (now trusted) source
    flag.source_ids = [sid for sid in trusted.source_ids if sid not in flag.source_ids] + flag.source_ids
    flag.rule_note = c.note + f"; confirmed by a trusted source (was {before} from an unverified site)"


# -- 5. dig deeper -------------------------------------------------------------


def _followup_step(st: _State, entity: ConfirmedEntity) -> None:
    b = st.cfg.settings.budget
    candidates = [f for f in sort_flags(st.flags) if f.colour in ("red", "amber") and not f.stale]
    if not candidates or b.max_followups <= 0:
        st.emit("followup", "No red or watch items to dig into.")
        return
    shown = candidates[:6]
    lines = "\n".join(f"- id={f.id} colour={f.colour} area={f.area} date={f.event_date or 'unknown'} "
                      f"sources={len(f.source_ids)} trust={f.trust}{' (capped from red)' if f.capped_unverified else ''} "
                      f"summary={f.summary}" for f in shown)
    country = entity.country_name or entity.country_code or "unknown"
    max_words = st.cfg.settings.max_query_extra_words
    user = (f"Company: {entity.legal_name}\nCountry: {country}\nPick at most {b.max_followups} flags.\n"
            f"Queries: the company name plus at most {max_words} words.\n\nVerified flags:\n{lines}\n")
    picks: list[tuple[Flag, str, str, str]] = []
    valid = {f.id: f for f in shown}

    def fallback_query(f: Flag) -> str:
        return f"{entity.legal_name} {f.event_type.replace('_', ' ')}"

    def short(q: str, f: Flag) -> str:
        q = " ".join(q.split())[:150]
        return q if q and _extra_words(q, entity) <= max_words else fallback_query(f)

    try:
        out = _bounded(st, st.llm.structured, role="verifier", system=_system("followup"), user=user, schema=FollowupOutput)
        for p in out.picks:
            if p.flag_id in valid and all(p.flag_id != x[0].id for x in picks):
                f0 = valid[p.flag_id]
                picks.append((f0, " ".join(p.question.split())[:200], short(p.query, f0), short(p.query_local, f0)))
    except LLMError as exc:
        st.result.stats.llm_errors += 1
        st.warn(f"Follow-up picker failed; using rule-based choice: {exc}")
    if not picks:  # deterministic fallback: red flags, then unverified items capped from red
        serious = [c for c in candidates if c.colour == "red"] + [c for c in candidates if c.capped_unverified and c.colour == "amber"]
        for f in serious[: b.max_followups]:
            q = fallback_query(f)
            picks.append((f, "Is there more recent or corroborating information?", q, q))

    english = _english_speaking(st, entity)
    for n, (flag, question, query, query_local) in enumerate(picks[: b.max_followups], start=1):
        st.check_time()
        if not st.budget.take_followup():
            break
        same = english or _norm_name(query_local) == _norm_name(query)
        fu = Followup(id=f"followup-{n}", flag_id=flag.id, flag_summary=flag.summary, question=question, query=query,
                      query_local="" if same else query_local)
        st.result.followups.append(fu)
        st.emit("followup", f"Digging deeper on: {flag.summary} — {question}", followup_id=fu.id, flag_id=flag.id, query=query,
                query_local=fu.query_local)
        tiers: list[TierId] = [t for t in ("official", "major_news", "rail_trade", "company_own") if st.allowlist.domains_for([t])]
        # Trusted sources only, in English and (when different) the local language: local press
        # and registers often report the outcome first, in their own language.
        hits: list[tuple[SearchHit, SourceMatch]] = []
        for suffix, q, lang in (("", query, "en"), ("-local", fu.query_local, "local")):
            if not q:
                continue
            item = PlannedSearch(id=fu.id + suffix, umbrella=flag.area, purpose=f"Follow-up on {flag.id}: {question}",
                                 query=q, tiers=tiers, topic="general", start_date=_start_date(st, "legal"),
                                 lang=cast(Literal["en", "local"], lang))
            st.result.plan.append(item)
            for h, m in _run_search(st, item, st.allowlist):
                if h.url not in st.seen_urls and all(h.url != x.url for x, _ in hits):
                    hits.append((h, m))
                else:
                    _drop(st, item, h, "duplicate")
        hits.sort(key=lambda hm: _hit_key(st, None, hm[0], hm[1]))
        fu_plan = next(p for p in st.result.plan if p.id == fu.id)
        for h, _ in hits[b.pages_per_followup:]:
            _drop(st, fu_plan, h, "page_budget")
        hits = hits[: b.pages_per_followup]
        granted = st.budget.take_extracts(len(hits), keep_for_followups=False)
        fu_item = next(p for p in st.result.plan if p.id == fu.id)
        chosen = [(fu_item, h, m) for h, m in hits[:granted]]
        for _, h, _ in chosen:
            st.seen_urls.add(h.url)
        pages = _fetch_pages(st, chosen, found_by_override=fu.id)
        fu.pages_checked = len(pages)
        before = set(flag.source_ids)
        before_colour, before_trust = flag.colour, flag.trust
        claim = (flag.id, flag.summary) if flag.trust == "unverified" else None
        found = _analyse_pages(st, pages, followup_id=fu.id, claim_under_check=claim)
        if flag.id in st.contradicted:
            _mark_contradicted(flag)
            fu.outcome = "A trusted source states the opposite; the claim is no longer a watch item. "
        fu.corroborating_source_ids = [s for s in flag.source_ids if s not in before]
        if before_trust == "unverified" and flag.trust == "trusted" and flag.colour != before_colour:
            fu.outcome = f"Re-rated from {_COLOUR_WORD[before_colour]} to {_COLOUR_WORD[flag.colour]}. "
        fu.new_flag_ids = sorted({f.id for f in found if f.id != flag.id}, key=lambda x: int(x[1:]))
        fu.outcome += _followup_outcome(st, fu)
        st.emit("followup", f"Follow-up result: {fu.outcome}", followup_id=fu.id)


def _mark_contradicted(flag: Flag) -> None:
    """Gate E7: a trusted page states the opposite. Kept on record, no longer flagged."""
    flag.signals.contradicted_by_trusted = True
    if flag.colour in ("red", "amber", "green"):
        flag.rule_note += f"; contradicted by a trusted source: {flag.colour} → neutral"
        flag.colour = "neutral"
    flag.knockout = False


_COLOUR_WORD = {"red": "red flag", "amber": "watch item", "green": "strength", "neutral": "not flagged"}


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
    _fill_corroboration(st)
    if r.stats.drop_reasons:
        counts = ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in sorted(r.stats.drop_reasons.items()))
        st.emit("report", f"Results not read, by reason: {counts}.", drop_reasons=dict(r.stats.drop_reasons))
    flags = sort_flags(st.flags)
    r.flags = flags
    used_ids = {sid for f in flags for sid in f.source_ids}
    ordered_sources = sorted(st.sources.values(), key=lambda s: int(s.id[1:]))
    r.sources = ordered_sources
    pages_by_area: dict[str, int] = {}
    unverified_by_area: dict[str, int] = {}
    for s in ordered_sources:
        if s.umbrella:
            bucket = pages_by_area if s.trust == "trusted" else unverified_by_area
            bucket[s.umbrella] = bucket.get(s.umbrella, 0) + 1
    labels: dict[str, str] = {u: st.cfg.settings.umbrellas[u].label for u in UMBRELLAS}
    r.areas = area_statuses(flags, pages_by_area, labels, unverified_by_area,
                            source_trust={s.id: s.trust for s in ordered_sources})
    _score(st, flags, ordered_sources)
    # "Not enough evidence" means no TRUSTED page about the company was read. Unverified pages
    # alone do not count, and neither do the country figures (they describe the country).
    data_ids = {s.id for s in ordered_sources if s.text_origin == "data"}
    company_pages = r.stats.trusted_pages_read - len(data_ids)
    company_flags = [f for f in flags if not set(f.source_ids) <= data_ids]
    if company_pages == 0 and not company_flags:
        r.verdict = rules.verdict.no_evidence
    else:
        r.verdict = overall_verdict(flags, rules, pages_read=company_pages)
    r.next_steps = next_steps(flags, rules)
    not_assessed = [a.label for a in r.areas if a.status == "not_assessed"]
    publishers = sorted({s.publisher for s in ordered_sources if s.trust == "trusted"})
    unverified_sites = sorted({s.publisher for s in ordered_sources if s.trust == "unverified"})
    dropped = r.stats.results_dropped_not_allowlisted + r.stats.results_dropped_denylisted
    r.limits = [
        f"Checked {plural(r.stats.trusted_pages_read, 'page')} from {plural(len(publishers), 'trusted publisher')}"
        + (f" and {plural(r.stats.unverified_pages_read, 'page')} from {plural(len(unverified_sites), 'unverified site')}"
           if unverified_sites else "")
        + f"; {plural(dropped, 'result')} from off-list or blocked sites ignored."
        + (f" Not assessed: {', '.join(not_assessed)}." if not_assessed else ""),
        "Automated public-source research, not independent verification or supplier qualification; "
        f"{plural(len(r.rejected), 'unsupported, off-topic or namesake fact')} discarded.",
        "Not linked to the anonymised SUPP_* records in the supplier catalogue.",
    ]
    if r.status == "partial":
        r.limits[0] += " The run hit its time limit, so coverage is incomplete."
    if write_summary and flags:
        r.summary = _write_summary(st, flags)
    if not r.summary:
        r.summary = _fallback_summary(flags, r.stats.trusted_pages_read, not_assessed)
    st.emit("report", "Report ready.", verdict=r.verdict, flags=len(flags), cited_sources=len(used_ids))


def _score(st: _State, flags: list[Flag], sources: list[Source]) -> None:
    """Numbers -> ScoringInputs -> detailed score. The report shows the card; result.json keeps
    the inputs and the full breakdown for "How was this scored?"."""
    r = st.result
    for s in sources:
        if s.trust == "unverified":
            s.reliability = "C" if source_reliability([s], st.page_texts)[s.id] == "C" else "D"
    accept_pages(st.numbers, flags)
    r.numeric_facts = list(st.numbers)
    country: list[dict[str, Any]] = []
    url_to_id = {s.url: s.id for s in sources}
    for f in flags:
        if f.data and f.area == "country":
            for fig in f.data.get("figures", []):
                sid = url_to_id.get(str(fig.get("source_url")))
                quote = str(fig.get("quote") or f"{fig.get('indicator')} {fig.get('value')}")
                country.append({**fig, "source_id": sid, "quote": quote})
    try:
        inputs = build_inputs(st.numbers, flags, sources, country, st.page_texts,
                              st.cfg.settings.injury_benchmarks, st.entity.country_code if st.entity else "")
        r.scoring_inputs = inputs.model_dump(mode="json")
        rep = score_detailed(flags, r.areas, st.cfg.scoring, inputs=inputs, rules=st.cfg.rules, as_of=st.today,
                             sources=sources)
        r.scores = rep.card.model_copy(update={"coverage": rep.coverage, "range_low": rep.range_low,
                                               "range_high": rep.range_high})
        r.scoring_detail = rep.model_dump(mode="json")
    except (ConfigError, ValueError, KeyError) as exc:
        st.warn(f"Scoring failed, scores not shown: {type(exc).__name__}: {exc}")
        r.scores = score_result(flags, r.areas, None)


def _fill_corroboration(st: _State) -> None:
    """Code-computed grading signals: independent domains (syndicated copies count once) and
    whether a trusted source independently corroborates the fact."""
    for f in st.flags:
        srcs = [st.sources[sid] for sid in f.source_ids if sid in st.sources]
        if not srcs:
            continue
        groups = independent_groups([(domain_of(s.url), st.page_shingles.get(s.id, frozenset())) for s in srcs],
                                    passages=[shingles(st.page_texts.get(s.id, ""), COPY_PASSAGE_WORDS) for s in srcs])
        f.signals.independent_domains = len(groups)
        f.signals.corroborated_by_trusted = len(groups) >= 2 and any(
            srcs[i].trust == "trusted" for g in groups for i in g)


def _write_summary(st: _State, flags: list[Flag]) -> str:
    assert st.entity is not None
    facts = [{"colour": f.colour, "area": f.area, "status": f.claim_status, "date": f.event_date,
              "company_stated": f.company_stated, "source_trust": f.trust, "finding": f.summary}
             for f in flags if f.colour != "neutral"][:15]
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
    if re.search(r"\bno risks?\b|\brated as\b", text, re.IGNORECASE):
        return ""  # never claim "no risk"; "rated as <verdict label>" reads badly -> template summary
    return text[:700]


def _fallback_summary(flags: list[Flag], pages: int, not_assessed: list[str]) -> str:
    """Template summary: the verdict in plain words first, then counts, then gaps."""
    n = {c: sum(1 for f in flags if f.colour == c) for c in ("red", "amber", "green")}
    if any(f.knockout for f in flags):
        lead = "A knock-out risk was found."
    elif n["red"]:
        lead = f"{'A red flag was' if n['red'] == 1 else 'Red flags were'} found."
    elif n["amber"]:
        items = "is 1 item" if n["amber"] == 1 else f"are {n['amber']} items"
        lead = f"No red flags were found, but there {items} to watch."
    elif pages == 0:
        lead = "There is not enough evidence: no trusted source returned usable results."
    else:
        lead = "No red flags or watch items were found in the sources checked."
    text = (f"{lead} Found {plural(n['red'], 'red flag')}, {plural(n['amber'], 'watch item')} and "
            f"{plural(n['green'], 'strength')} in {plural(pages, 'trusted source')}.")
    if not_assessed:
        text += f" Not assessed, so nothing is known yet about: {', '.join(not_assessed)}."
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
