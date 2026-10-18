"""Thin bridge between the web app (``supplier_app``) and the research pipeline.

The app sees one "run" dict per research request, polled over HTTP. This module:

* keeps runs and saved research suppliers in ``<data-dir>/state.json`` (same layout as before,
  so approvals, the workspace and older saved runs keep working);
* starts ``run_research(company, country, website)`` in a worker thread and maps its progress
  events and its ``ResearchResult`` onto the run dict (scores, TL;DR points with citation
  numbers, citations with exact quotes, scoring breakdown, flags, timeline);
* writes ``report.html``, ``report.md`` and ``result.json`` next to ``state.json`` under
  ``runs/<id>/`` so ``state.json`` stays small.

Only the standard library is imported at module level: the research dependencies (pydantic,
anthropic, PyYAML) are imported when a run starts, so the catalogue and data chat still work
without them. Offline mode (``offline_fixture=True``) runs the real pipeline on the invented
fixture with fake search and model clients: no keys, no network, no cost.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import threading
import time
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, cast

ROOT = Path(__file__).resolve().parents[1]
AREAS = ["financial", "legal", "country", "people", "operations", "reputation"]
AREA_LABELS = {
    "financial": "Financial", "legal": "Legal & Governance", "country": "Country & Location",
    "people": "People & Safety", "operations": "Operations & Delivery", "reputation": "Reputation & Outside View",
}
SCHEMA = "research-run-v2"
MAX_ACTIVE_RUNS = 2
MAX_POINTS = 5
FIXTURE_COMPANY = ("Veltrava Rail Components", "DE", "veltrava-rail.example")
FIXTURE_NOTICE = ("Offline example: Veltrava Rail Components GmbH is a fictional company. "
                  "No live search was performed.")
TRUST_LABELS = {
    "trusted": "Trusted source",
    "company_stated": "Trusted source · the company's own statement",
    "unverified": "🟨 Not in our trusted source list",
}
UNAVAILABLE = "Live research is unavailable: configure ANTHROPIC_API_KEY and TAVILY_API_KEY on the local server."
RESEARCH_ENV = ("ANTHROPIC_API_KEY", "TAVILY_API_KEY")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text(value: Any, limit: int = 4000) -> str:
    return value[:limit] if isinstance(value, str) else ""


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def safe_url(value: Any) -> str:
    """Display-only public http(s) links; the server never fetches caller URLs."""
    if not isinstance(value, str):
        return ""
    try:
        parsed = urllib.parse.urlsplit(value.strip())
        host = parsed.hostname or ""
        if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            if host.lower() == "localhost" or host.endswith((".local", ".localhost")):
                return ""
        return value.strip()[:2000]
    except (ValueError, TypeError):
        return ""


def website_hint(value: Any) -> str:
    """A website hint as typed ("knorr-bremse.com" or a full URL); empty if unsafe."""
    raw = text(value, 300).strip()
    if not raw:
        return ""
    return safe_url(raw if "://" in raw else "https://" + raw)


def load_env(env: dict[str, str] | None) -> None:
    """Our config and SDK clients read os.environ; copy the research keys there (never overwrite)."""
    for key, value in (env or {}).items():
        if value and (key in RESEARCH_ENV or key.startswith("RESEARCH_")):
            os.environ.setdefault(key, value)


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class Store:
    """Runs and saved research suppliers in ``state.json`` (atomic rewrite)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.data: dict[str, dict[str, Any]] = {"runs": {}, "suppliers": {}}
        file = self.path / "state.json"
        if file.is_file():
            self.data = json.loads(file.read_text(encoding="utf-8"))
            self.data.setdefault("runs", {})
            self.data.setdefault("suppliers", {})
        # An interrupted worker cannot continue after a restart.
        for run in self.data["runs"].values():
            if run.get("status") in {"queued", "researching"}:
                run.update(status="failed", error="The local server stopped during this run. Start a new run to retry.")
        self.flush()

    def flush(self) -> None:
        temporary = self.path / "state.json.tmp"
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, self.path / "state.json")

    def run_dir(self, run_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise KeyError("Research run not found")
        return self.path / "runs" / run_id

    def put(self, run: dict[str, Any]) -> None:
        with self.lock:
            self.data["runs"][run["id"]] = _copy(run)
            self.flush()

    def get(self, run_id: str) -> dict[str, Any]:
        with self.lock:
            if run_id not in self.data["runs"]:
                raise KeyError("Research run not found")
            return cast(dict[str, Any], _copy(self.data["runs"][run_id]))

    def runs(self) -> list[dict[str, Any]]:
        keys = ("id", "company", "country", "mode", "status", "created_at", "completed_at", "summary", "verdict",
                "demo", "notice", "schema_version")
        with self.lock:
            rows = []
            for run in reversed(list(self.data["runs"].values())):
                row = {k: run.get(k) for k in keys}
                scores = run.get("scores") or {}
                row["score"] = {"total": scores.get("total"), "level": scores.get("level"),
                                "assessed": scores.get("assessed"), "areas": [
                                    {"area": a.get("area"), "score": a.get("score"), "coverage": a.get("coverage")}
                                    for a in scores.get("areas") or []]} if scores else None
                row["tone"] = (run.get("tldr") or {}).get("tone")
                row["flag_counts"] = (run.get("tldr") or {}).get("counts")
                row["has_report"] = bool((run.get("report") or {}).get("html"))
                rows.append(row)
            return rows

    def file(self, run_id: str, name: str) -> str:
        path = self.run_dir(run_id) / name
        if not path.is_file():
            raise KeyError("Report not found")
        return path.read_text(encoding="utf-8")

    def suppliers(self) -> list[dict[str, Any]]:
        with self.lock:
            return cast(list[dict[str, Any]], _copy(list(self.data["suppliers"].values())))

    def save_supplier(self, run_id: Any) -> tuple[dict[str, Any], bool]:
        if not isinstance(run_id, str):
            raise ValueError("run_id is required")
        with self.lock:
            run = self.get(run_id)
            if run["status"] != "completed":
                raise ValueError("Only a completed research report can be saved")
            # Context is part of identity: never silently merge different components/entities.
            identity = "|".join(normalized(str(run.get(k) or "")) for k in ("company", "country", "website", "scope"))
            identity += "|saved_fixture" if run.get("demo") else "|public_research"
            supplier_id = hashlib.sha256(identity.encode()).hexdigest()[:20]
            existing = self.data["suppliers"].get(supplier_id)
            if existing:
                # A newer report of the same company replaces the linked report.
                if existing.get("run_id") != run_id:
                    existing.update(run_id=run_id, summary=run.get("summary", ""),
                                    agent_scores=_copy(run.get("scores")), verdict=run.get("verdict", ""))
                    self.flush()
                return _copy(existing), False
            record = {"id": supplier_id, "company": run["company"], "country": run.get("country", ""),
                      "website": run.get("website", ""), "scope": run.get("scope", ""), "run_id": run_id,
                      "added_at": now(), "summary": run.get("summary", ""), "legacy_scores": None,
                      "actions": _copy(run.get("actions", [])), "demo": bool(run.get("demo"))}
            record.update(schema_version="research-supplier-v1",
                          provenance="saved_fixture" if run.get("demo") else "public_research",
                          entity=_copy(run.get("entity", {})),
                          # The CSV-compatible columns stay empty: public-research scores are a
                          # different method and are never mixed with the dataset scores.
                          numeric_scores={**{a: None for a in AREAS}, "total": None},
                          agent_scores=_copy(run.get("scores")), verdict=run.get("verdict", ""))
            self.data["suppliers"][supplier_id] = record
            self.flush()
            return _copy(record), True

    def action(self, supplier_id: str, action_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            supplier = self.data["suppliers"].get(supplier_id)
            if not supplier:
                raise KeyError("Supplier not found")
            action = next((a for a in supplier["actions"] if a["id"] == action_id), None)
            if not action:
                raise KeyError("Action not found")
            if not any(field in values for field in ("status", "owner")):
                raise ValueError("Provide an action status or owner")
            if "status" in values:
                if values["status"] not in {"open", "done"}:
                    raise ValueError("Action status must be open or done")
                action["status"] = values["status"]
            if "owner" in values:
                action["owner"] = text(values["owner"], 200)
            self.flush()
            return cast(dict[str, Any], _copy(action))


# ---------------------------------------------------------------------------
# Progress events -> run
# ---------------------------------------------------------------------------


def _area_of_step(step: str) -> str | None:
    head = step.split("-", 1)[0]
    return head if head in AREAS else None


def empty_progress() -> dict[str, Any]:
    return {"step": "queued", "areas": {a: {"planned": 0, "searched": 0, "failed": 0} for a in AREAS},
            "pages_read": 0, "facts_verified": 0}


def apply_event(run: dict[str, Any], kind: str, message: str, data: dict[str, Any]) -> None:
    """Map one ProgressEvent onto the run (events[], plan[], progress)."""
    entry: dict[str, Any] = {"at": now(), "stage": kind, "message": text(message, 600)}
    progress = run.setdefault("progress", empty_progress())
    area = None
    if kind == "identity":
        progress["step"] = "identity"
    elif kind == "plan":
        progress["step"] = "search"
        steps = data.get("steps") or []
        grouped: dict[str, list[str]] = {a: [] for a in AREAS}
        for p in run.get("plan", []):
            grouped.setdefault(p["category"], []).extend(p.get("questions", []))
        for s in steps:
            a = s.get("area")
            if a in grouped and s.get("query") and s["query"] not in grouped[a]:
                grouped[a].append(str(s["query"]))
                progress["areas"][a]["planned"] += 1
        run["plan"] = [{"category": a, "questions": grouped[a]} for a in AREAS]
    elif kind == "search":
        area = _area_of_step(str(data.get("step") or ""))
        if area:
            progress["areas"][area]["searched"] += 1
            entry["message"] = f"{area}: {entry['message']}"
        if str(data.get("step") or "").startswith("followup"):
            progress["step"] = "followup"
    elif kind == "extract":
        progress["step"] = "read" if progress["step"] != "followup" else "followup"
        urls = data.get("urls")
        if isinstance(urls, list):
            progress["pages_read"] += len(urls)
    elif kind == "verify":
        if progress["step"] not in ("followup",):
            progress["step"] = "verify"
        m = re.search(r"(\d+) of \d+ facts verified", message)
        if m:
            progress["facts_verified"] += int(m.group(1))
    elif kind == "followup":
        progress["step"] = "followup"
    elif kind == "report":
        progress["step"] = "report"
    elif kind == "warning":
        if message.startswith(("Search failed", "Could not read")):
            entry["stage"] = "search_error"
            m = re.search(r"\b(financial|legal|country|people|operations|reputation)-", message)
            if m:
                area = m.group(1)
                progress["areas"][area]["failed"] += 1
                entry["message"] = f"{area}: {entry['message']}"
    elif kind == "done":
        entry["stage"] = "complete"
        progress["step"] = "done"
    if area:
        entry["area"] = area
    run.setdefault("events", []).append(entry)
    run["events"] = run["events"][-200:]


def initial_plan() -> list[dict[str, Any]]:
    return [{"category": a, "questions": []} for a in AREAS]


# ---------------------------------------------------------------------------
# ResearchResult -> run
# ---------------------------------------------------------------------------


def _scores(result: Any) -> dict[str, Any]:
    card = result.scores
    by_area = {a.area: a for a in card.areas}
    status = {a.area: a for a in result.areas}
    areas = []
    for a in AREAS:
        s = by_area.get(a)
        coverage = s.coverage if s else "not_assessed"
        score = s.score if s and coverage != "not_assessed" else None  # Not assessed is never 0
        areas.append({"area": a, "label": AREA_LABELS[a], "score": score,
                      "level": s.level if s and score is not None else None, "coverage": coverage,
                      "trusted_pages": s.trusted_pages if s else 0, "unverified_pages": s.unverified_pages if s else 0,
                      "status": status[a].status if a in status else "not_assessed",
                      "method": s.method if s else "not scored: area not assessed"})
    assessed = sum(1 for a in areas if a["coverage"] != "not_assessed")
    return {"scale": "0 = no risk, 100 = maximum risk", "total": card.total, "level": card.total_level,
            "coverage_pct": round(card.coverage * 100) if isinstance(card.coverage, (int, float)) else None,
            "range": [card.range_low, card.range_high] if card.range_low is not None and card.range_high is not None else None,
            "method": card.total_method, "weights": dict(card.weights), "assessed": assessed, "areas": areas,
            "label": "Public research score, not comparable to dataset scores"}


def _citation_dict(c: Any, flag: Any | None) -> dict[str, Any]:
    d = c.to_dict()
    url = safe_url(d.get("url"))
    link = d.get("link") or ""
    link = link if url and link.startswith(url.split("#", 1)[0]) and safe_url(link) and len(link) <= 2600 else url
    return {"n": d["id"], "source_id": d["source_id"], "flag_id": d.get("flag_id"), "url": url, "link": link,
            "title": d.get("title") or d.get("publisher") or "Source", "publisher": d.get("publisher") or "",
            "published": d.get("published"), "accessed": d.get("accessed"), "trust": d.get("trust"),
            "trust_label": TRUST_LABELS.get(str(d.get("trust")), TRUST_LABELS["unverified"]),
            "quote": d.get("quote") or "", "excerpt": d.get("excerpt") or "", "quote_start": d.get("quote_start", 0),
            "quote_end": d.get("quote_end", 0), "context_found": bool(d.get("context_found")),
            "area": flag.area if flag is not None else None,
            "area_label": AREA_LABELS.get(flag.area) if flag is not None else None,
            "colour": flag.colour if flag is not None else None}


def _shorten(value: str, words: int = 24) -> str:
    parts = " ".join(value.split()).rstrip(".").split()
    return " ".join(parts) if len(parts) <= words else " ".join(parts[:words]).rstrip(",;:") + "…"


class _Cit:
    """Fallback citation (used only if the report module's citation index is unavailable)."""

    def __init__(self, num: int, source: Any, flag: Any | None, page_text: str) -> None:
        self.num, self.source_id, self.flag_id = num, source.id, flag.id if flag is not None else None
        quote = " ".join(flag.quote.split()) if flag is not None else ""
        context = (flag.quote_context or "") if flag is not None else ""
        hay = context if quote and quote in context else page_text if quote and quote in page_text else ""
        start = hay.find(quote) if hay else -1
        lo = max(0, start - 200) if start >= 0 else 0
        excerpt = hay[lo:start + len(quote) + 200] if start >= 0 else quote
        q0 = start - lo if start >= 0 else 0
        words = quote.split()
        frag = ""
        if words:
            parts = [" ".join(words)] if len(words) <= 8 else [" ".join(words[:4]), " ".join(words[-4:])]
            frag = "#:~:text=" + ",".join(urllib.parse.quote(x, safe="") for x in parts)
        trust = "unverified" if source.trust == "unverified" else "company_stated" if source.tier == "company_own" else "trusted"
        self.d = {"id": num, "source_id": source.id, "flag_id": self.flag_id, "url": source.url,
                  "link": source.url.split("#", 1)[0] + frag if frag else source.url, "title": source.title,
                  "publisher": source.publisher, "published": source.published_date,
                  "accessed": source.retrieved_at[:10], "trust": trust, "quote": quote, "excerpt": excerpt,
                  "quote_start": q0, "quote_end": q0 + len(quote), "context_found": start >= 0}

    def to_dict(self) -> dict[str, Any]:
        return dict(self.d)


class _FallbackIndex:
    def __init__(self, r: Any, page_texts: dict[str, str]) -> None:
        self.by_id = {s.id: s for s in r.sources}
        self.texts = page_texts
        self._made: dict[tuple[str, str | None], _Cit] = {}

    def _get(self, sid: str, f: Any | None) -> _Cit:
        key = (sid, f.id if f is not None else None)
        if key not in self._made:
            self._made[key] = _Cit(len(self._made) + 1, self.by_id[sid], f, self.texts.get(sid, ""))
        return self._made[key]

    def for_flag(self, f: Any) -> list[_Cit]:
        ids = [x for x in f.source_ids if x in self.by_id]
        return [self._get(ids[0], f)] + [self._get(x, None) for x in ids[1:]] if ids else []

    def all(self) -> list[_Cit]:
        return list(self._made.values())


def _tone(r: Any) -> str:
    if any(f.knockout for f in r.flags):
        return "critical"
    for colour in ("red", "amber", "green"):
        if any(f.colour == colour for f in r.flags):
            return colour
    return "neutral"


def build_view(result: Any, page_texts: dict[str, str] | None = None) -> dict[str, Any]:
    """Everything the app shows, computed once from the result. Deterministic.

    Uses the report module's citation index (same quote context and deep links as the report)
    when available, and a small local fallback otherwise, so the chat never breaks while the
    report layout changes."""
    r = result
    try:
        from .report_html import CitationIndex, load_input

        r, ev = load_input(result, page_texts)
        idx: Any = CitationIndex(r, ev, numbering="passage")
    except Exception:
        idx = _FallbackIndex(r, dict(page_texts or {}))
    try:
        from .report_html import verdict_tone
        tone = verdict_tone(r)
    except Exception:
        tone = _tone(r)
    from .rules import sort_flags

    ranked = sort_flags(list(r.flags))
    flags_by_id = {f.id: f for f in r.flags}
    reds = [f for f in ranked if f.colour == "red"]
    ambers = [f for f in ranked if f.colour == "amber"]
    greens = [f for f in ranked if f.colour == "green"]
    # The same balanced points as report section 1 (red, then watch, then strengths; at most
    # 2 per area and 5 in total), so the card and the report never disagree.
    from .report_html import key_points

    chosen = key_points(r)[:MAX_POINTS]
    # Company intro (quote-checked profile only); first on the card, so numbered first.
    intro: list[dict[str, Any]] = []
    if r.status in ("ok", "partial") and hasattr(idx, "for_quote"):
        from .report_data import intro_parts

        for part in intro_parts(r):
            cs = idx.for_quote(part["source_ids"], part["quote"], f"profile:{part['key']}")[:1]
            intro.append({"key": part["key"], "text": part["text"], "citations": [c.num for c in cs]})
    points = []
    for f in chosen:
        cites = [c.num for c in idx.for_flag(f)][:3]
        points.append({"flag_id": f.id, "colour": f.colour, "kind": {"red": "red_flag", "amber": "watch",
                       "green": "strength"}.get(f.colour, "context"), "text": _shorten(f.summary),
                       "date": f.event_date, "area": f.area, "area_label": AREA_LABELS[f.area],
                       "trust": f.trust, "alleged": f.claim_status == "alleged", "citations": cites})
    # Every other flag gets numbers too, so the report view and chat answers can cite them.
    flag_cites: dict[str, list[int]] = {}
    for f in ranked:
        flag_cites[f.id] = [c.num for c in idx.for_flag(f)]
    base = scoring = None
    if r.status in ("ok", "partial"):
        try:
            from .tldr import tldr_data

            base = tldr_data(r, page_texts=page_texts)
        except Exception:
            base = None
        try:
            from .tldr import score_explainer

            scoring = score_explainer(r, r.scoring_detail, page_texts)
        except Exception:
            scoring = None
    if scoring is not None:
        remap: dict[int, int] = {}
        for c in scoring.get("citations", []):
            cf = flags_by_id.get(c.get("flag_id")) if c.get("flag_id") else None
            if c.get("source_id") in idx.by_id:
                remap[c["id"]] = idx._get(c["source_id"], cf).num  # same numbers as the card
        for area in scoring.get("areas", []):
            for sub in area.get("sub_scores", []):
                for line in sub.get("lines", []):
                    line["citations"] = [remap[n] for n in line.get("citations", []) if n in remap]
        scoring.pop("citations", None)
        scoring["method"] = ("Each fact becomes points through a published method where one exists (credit rating "
                             "scales, Altman Z, World Bank and Transparency International indices), then the areas are "
                             "weighted like the catalogue's six areas. Areas without evidence are Not assessed, never 0.")
        scoring["label"] = "Public research score, not comparable to dataset scores"
    citations = []
    for c in idx.all():
        citations.append(_citation_dict(c, flags_by_id.get(c.flag_id) if c.flag_id else None))
    flags = [{"id": f.id, "colour": f.colour, "area": f.area, "area_label": AREA_LABELS[f.area],
              "summary": f.summary, "date": f.event_date, "trust": f.trust, "claim_status": f.claim_status,
              "event_type": f.event_type, "knockout": f.knockout, "stale": f.stale, "company_stated": f.company_stated,
              "rule_note": f.rule_note, "citations": flag_cites.get(f.id, []), "source_ids": list(f.source_ids)}
             for f in ranked]
    timeline = sorted(({"date": f["date"], "colour": f["colour"], "summary": f["summary"], "flag_id": f["id"],
                        "area": f["area"]} for f in flags if f["date"]), key=lambda e: str(e["date"]), reverse=True)
    counts = {"red": len(reds), "amber": len(ambers), "green": len(greens)}
    tldr = {"verdict": r.verdict, "tone": tone, "summary": r.summary, "intro": intro, "points": points,
            "counts": counts, "not_assessed": [AREA_LABELS[a.area] for a in r.areas if a.status == "not_assessed"],
            "score_text": base["score"].get("text") if base and isinstance(base.get("score"), dict) else None,
            "text": base.get("text") if base else r.summary}
    return {"tldr": tldr, "citations": citations, "scoring": scoring, "flags": flags, "timeline": timeline,
            "scores": _scores(r)}


def run_from_result(run: dict[str, Any], result: Any, page_texts: dict[str, str] | None,
                    out_dir: Path | None) -> None:
    """Fill the run dict from a finished ResearchResult (legacy fields + the new view)."""
    r = result
    status = {"ok": "completed", "partial": "completed", "needs_clarification": "needs_clarification",
              "error": "failed"}[r.status]
    run["status"] = status
    run["completed_at"] = now()
    run["schema_version"] = SCHEMA
    if r.notice:
        run["notice"] = r.notice
    if status == "failed":
        run["error"] = text("; ".join(r.warnings) or "Research failed.", 600)
        return
    if status == "needs_clarification" and r.clarification:
        run["clarification"] = {"question": r.clarification.question, "candidates": [
            {"legal_name": c.legal_name, "country_code": c.country_code, "country_name": c.country_name,
             "website": c.website, "description": c.description} for c in r.clarification.candidates[:6]]}
        run["summary"] = r.clarification.question
        return
    ent = r.entity
    if ent is not None:
        run["entity"] = {"requested_name": r.company_input, "legal_name": ent.legal_name,
                         "country_code": ent.country_code, "country_name": ent.country_name, "website": ent.website,
                         "verification": ("confirmed from sources" if ent.confirmed_by == "sources" else
                                          "confirmed from your input") + f": {ent.legal_name}"
                                         + (f" ({ent.country_name or ent.country_code})" if ent.country_name or ent.country_code else "")}
        run["company"] = ent.legal_name or run["company"]
    run["verdict"] = r.verdict
    run["summary"] = r.summary or r.verdict
    view = build_view(r, page_texts)
    run.update(view)
    quotes_by_source: dict[str, list[str]] = {}
    for f in r.flags:
        for sid in f.source_ids:
            quotes_by_source.setdefault(sid, []).append(f.quote)
    run["sources"] = [{"id": s.id, "title": s.title, "url": safe_url(s.url), "publisher": s.publisher,
                       "published_at": s.published_date, "accessed_at": s.retrieved_at, "kind": s.tier,
                       "trust": s.trust, "excerpt": " … ".join(quotes_by_source.get(s.id, []))[:1200]}
                      for s in r.sources]
    severity = {"high": "high", "medium": "moderate", "low": "low"}
    claim = {"confirmed": "disclosed", "alleged": "alleged", "unclear": "unknown"}
    run["findings"] = [{"id": f.id, "category": f.area, "title": f.summary, "detail": " ".join(x for x in (f.summary, f.rule_note) if x),
                        "severity": severity[f.severity], "colour": f.colour,
                        "confidence": "medium" if f.trust == "trusted" else "low", "status": claim[f.claim_status],
                        "source_ids": list(f.source_ids), "evidence": [{"source_id": f.source_ids[0], "quote": f.quote}] if f.source_ids else [],
                        "follow_up": next((fu.question for fu in r.followups if fu.flag_id == f.id), ""),
                        "trust": f.trust} for f in r.flags]
    run["categories"] = [{"id": a.area, "label": a.label, "assessment": a.status,
                          "confidence": "medium" if a.trusted_pages_used else "low", "summary": a.finding,
                          "finding_ids": list(a.flag_ids), "gaps": []} for a in r.areas]
    run["gaps"] = list(r.warnings) + [f"{a.label}: not assessed (no evidence found)." for a in r.areas if a.status == "not_assessed"]
    run["limitations"] = list(r.limits)
    red = any(f.colour == "red" or f.knockout for f in r.flags)
    run["actions"] = [{"id": f"A{i}", "category": "", "action": step, "priority": "high" if red else "normal",
                       "status": "open", "owner": ""} for i, step in enumerate(r.next_steps, 1)]
    run["next_steps"] = list(r.next_steps)
    failed = sorted({a for a, v in (run.get("progress") or {}).get("areas", {}).items() if v.get("failed")})
    run["coverage"] = {"state": "partial" if r.status == "partial" else "complete", "failed_search_categories": failed}
    if r.status == "partial":
        run["limitations"].insert(0, "Stopped at the time limit; findings so far.")
    run["usage"] = [r.stats.model_dump()]
    run["models"] = dict(r.models)
    if out_dir is not None:
        from .report import render_markdown
        from .report_html import render_html

        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.json").write_text(r.model_dump_json(indent=1), encoding="utf-8")
        (out_dir / "report.md").write_text(render_markdown(r), encoding="utf-8")
        (out_dir / "report.html").write_text(render_html(r, page_texts), encoding="utf-8")
        run["report"] = {"html": True, "md": True, "json": True}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ResearchService:
    """Starts runs in worker threads. ``llm``/``search``/``runner`` are injectable for tests."""

    def __init__(self, store: Store, env: dict[str, str] | None = None, *, llm: Any = None, search: Any = None,
                 runner: Callable[..., Any] | None = None, offline_fixture: bool = False,
                 fixture_delay_s: float = 0.0) -> None:
        self.store = store
        self.env = dict(env or {})
        self.llm, self.search, self.runner = llm, search, runner
        self.offline_fixture = offline_fixture or self.env.get("RESEARCH_OFFLINE_FIXTURE") == "1"
        self.fixture_delay_s = fixture_delay_s
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="research")
        self.lock = threading.Lock()
        load_env(self.env)

    # -- configuration ---------------------------------------------------
    def _deps(self) -> bool:
        try:
            import anthropic  # noqa: F401
            import pydantic  # noqa: F401
            import yaml  # noqa: F401
        except ImportError:
            return False
        return True

    def live_available(self) -> bool:
        if self.runner is not None or (self.llm is not None and self.search is not None):
            return True
        keys = all(self.env.get(k) or os.environ.get(k) for k in RESEARCH_ENV)
        return bool(keys and self._deps())

    def _budget(self) -> dict[str, Any]:
        try:
            from .config import load_settings

            s = load_settings()
            b, ow = s.budget, s.open_web
            searches = b.max_searches
            credits = searches * (2 if s.tavily.search_depth == "advanced" else 1)
            models = f"{s.models.gatherer} / {s.models.verifier}"
            return {"searches_max": searches, "pages_max": b.max_extracts, "followups_max": b.max_followups,
                    "seconds": [int(b.wall_clock_seconds * 2 / 3), int(b.wall_clock_seconds)],
                    "tavily_credits": credits, "open_web_searches": ow.max_searches if ow.enabled else 0,
                    "models": models}
        except Exception:  # config or dependencies missing: show a plain estimate
            return {"searches_max": 22, "pages_max": 19, "followups_max": 2, "seconds": [80, 120],
                    "tavily_credits": 44, "open_web_searches": 2, "models": ""}

    def config(self) -> dict[str, Any]:
        budget = self._budget()
        return {"live_available": self.live_available(), "offline_fixture": self.offline_fixture,
                "search_engine": "Tavily", "model": budget.get("models", ""),
                "categories": [{"id": a, "label": AREA_LABELS[a]} for a in AREAS],
                "modes": {"basic": "Searches each area once, no follow-ups", "deep": "Searches each area and follows up red flags"},
                "demo_company": "Veltrava Rail Components GmbH (fictional)",
                "budgets": budget,
                "estimate_note": (f"Takes about {budget['seconds'][0]}–{budget['seconds'][1]} seconds and uses up to "
                                  f"{budget['searches_max']} web searches. Public sources only; the result is kept "
                                  "apart from the catalogue scores."),
                "evidence_policy": "Every finding is backed by an exact quote from its source."}

    # -- runs --------------------------------------------------------------
    def start(self, values: dict[str, Any]) -> str:
        company = text(values.get("company"), 200).strip()
        demo = values.get("demo", False)
        if not isinstance(demo, bool):
            raise ValueError("demo must be true or false")
        fixture = demo or self.offline_fixture
        if not company and not fixture:
            raise ValueError("Enter a company name")
        mode = values.get("mode", "deep")
        if mode not in {"basic", "deep"}:
            raise ValueError("Mode must be basic or deep")
        if not fixture and not self.live_available():
            raise ValueError(UNAVAILABLE)
        dataset_context = values.get("dataset_context", [])
        if not isinstance(dataset_context, list) or len(dataset_context) > 20 or any(not isinstance(i, dict) for i in dataset_context):
            raise ValueError("dataset_context must be a bounded array of objects")
        if len(json.dumps(dataset_context, allow_nan=False)) > 12000:
            raise ValueError("dataset_context is too large")
        parent = values.get("parent_run_id")
        if parent is not None and (not isinstance(parent, str) or not re.fullmatch(r"[a-f0-9]{32}", parent)):
            raise ValueError("parent_run_id must be a run id")
        requested = company
        country, website = text(values.get("country"), 200).strip(), website_hint(values.get("website"))
        if fixture:
            company, country, website = FIXTURE_COMPANY[0], FIXTURE_COMPANY[1], "https://" + FIXTURE_COMPANY[2]
        with self.lock:
            active = sum(r["status"] in {"queued", "researching"} for r in self.store.runs())
            if active >= MAX_ACTIVE_RUNS:
                raise ValueError("Two research runs are already active. Wait for one to finish.")
            run: dict[str, Any] = {
                "id": uuid.uuid4().hex, "schema_version": SCHEMA, "status": "queued", "company": company,
                "requested_company": requested or company, "country": country, "website": website,
                "scope": text(values.get("scope"), 1600), "mode": mode, "demo": fixture, "created_at": now(),
                "events": [], "plan": initial_plan(), "progress": empty_progress(), "sources": [], "findings": [],
                "categories": [], "gaps": [], "actions": [], "summary": "", "verdict": "",
                "entity": {"requested_name": requested or company, "verification": "unverified"},
                "limitations": [], "legacy_scores": None, "usage": [], "dataset_context": dataset_context,
                "research_notes": [], "coverage": {"state": "pending", "failed_search_categories": []},
                "parent_run_id": parent, "notice": FIXTURE_NOTICE if fixture else None,
            }
            self.store.put(run)
            self.executor.submit(self._execute, run)
        return str(run["id"])

    def _clients(self, run: dict[str, Any]) -> dict[str, Any]:
        if run["demo"]:
            from .fakes import FakeLLM, FakeSearch, load_fixture

            fx = load_fixture()
            return {"llm": FakeLLM(fx), "search": FakeSearch(fx, delay_s=self.fixture_delay_s)}
        out: dict[str, Any] = {}
        if self.llm is not None:
            out["llm"] = self.llm
        if self.search is not None:
            out["search"] = self.search
        return out

    def _config(self, mode: str) -> Any:
        if mode != "basic":
            return None
        import dataclasses

        from .config import load_all

        cfg = load_all()
        budget = cfg.settings.budget.model_copy(update={"max_followups": 0})
        return dataclasses.replace(cfg, settings=cfg.settings.model_copy(update={"budget": budget}))

    def _execute(self, run: dict[str, Any]) -> None:
        lock = threading.Lock()
        last = [0.0]

        def on_progress(ev: Any) -> None:
            with lock:
                apply_event(run, ev.kind, ev.message, dict(ev.data))
                t = time.monotonic()
                if t - last[0] >= 0.4 or ev.kind in ("plan", "done", "identity"):
                    last[0] = t
                    self.store.put(run)

        try:
            run["status"] = "researching"
            self.store.put(run)
            runner: Callable[..., Any]
            if self.runner is not None:
                runner = self.runner
            else:
                from .orchestrator import run_research

                runner = run_research
            texts: dict[str, str] = {}
            kwargs: dict[str, Any] = {"on_progress": on_progress, "page_texts_out": texts, **self._clients(run)}
            cfg = self._config(run["mode"])
            if cfg is not None:
                kwargs["config"] = cfg
            result = runner(run["company"], run["country"] or None,
                            run["website"].split("://", 1)[-1] if run["website"] else None, **kwargs)
            if run["demo"]:
                result.notice = FIXTURE_NOTICE
            with lock:
                run_from_result(run, result, texts, self.store.run_dir(run["id"]))
        except Exception as error:  # never leave a run hanging
            run.update(status="failed", error=text(f"Research could not complete: {type(error).__name__}: {error}", 600))
            run.setdefault("events", []).append({"at": now(), "stage": "failed", "message": run["error"]})
        self.store.put(run)

    # -- chat over a finished run ------------------------------------------
    def chat(self, run_id: str, message: Any) -> dict[str, Any]:
        from .run_chat import chat, grounded_chat
        run = self.store.get(run_id)
        key = self.env.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        if run.get("demo") or (not key and self.llm is None):
            return chat(run, message)
        try:
            from .config import load_settings
            from .llm import AnthropicLLM
            settings = load_settings().models
            llm = self.llm or AnthropicLLM(
                gatherer_model=self.env.get("RESEARCH_GATHERER_MODEL") or settings.gatherer,
                verifier_model=self.env.get("RESEARCH_VERIFIER_MODEL") or settings.verifier,
                api_key=key, max_tokens=4096, timeout_s=45,
                gatherer_effort=settings.gatherer_effort)
            return grounded_chat(run, message, llm)
        except Exception:
            reply = chat(run, message)
            reply["answer"] = "The live answer model is unavailable; showing a saved-report lookup instead.\n\n" + reply["answer"]
            return reply
