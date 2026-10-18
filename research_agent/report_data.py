"""The report's ordered sections as plain data (JSON-ready). Deterministic.

The structure follows BAFA's risk-analysis guide (the German authority that enforces the
Supply Chain Act), used for all six risk areas. See docs/research/report-template-standard.md.
Both renderers (report_html.py, report.py) draw from :func:`report_sections`, and the web app
can render the same list, so every view shows the same sections in the same order:

    0 header · 1 summary · 2 profile · 3 country_sector · 4 company_risks · 5 weighting ·
    6 register · 7 prevention · 8 documentation · footer

Every section is always present. Missing data is shown as "Not found", "Not assessed" or
"Buyer input, not assessed", never as 0. Each citation is a full dict (number, link, quote,
excerpt with offsets, trust label), so a renderer needs nothing else.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast, get_args

from .dates import normalize_date
from .heatmap import HeatmapRule, describe, likelihood_of, load_rule, placed, severity_of
from .models import UMBRELLAS, AreaStatus, Flag, ProfileKey, ResearchResult, UmbrellaId
from .report_html import (
    AREA_LABELS,
    COLOUR_WORD,
    LEVEL_BANDS,
    NO_TOTAL_TEXT,
    TRUSTED_MARK,
    UNVERIFIED_MARK,
    UNVERIFIED_TEXT,
    Citation,
    CitationIndex,
    Evidence,
    area_score_value,
    area_scores,
    company_name,
    coverage_pct,
    is_scored,
    key_points,
    load_input,
    no_score_label,
    not_assessed_areas,
    override_notes,
    ranked_flags,
    score_line,
    score_range,
    timeline_events,
    verdict_tone,
)

ResultInput = ResearchResult | Mapping[str, Any] | str | Path

# Fixed area order of section 4 (and of the register's area column).
AREA_ORDER: tuple[UmbrellaId, ...] = ("operations", "financial", "people", "legal", "country", "reputation")

SECTIONS: tuple[tuple[str, int, str], ...] = (
    ("header", 0, "Supplier risk report"),
    ("summary", 1, "Summary for decision makers"),
    ("profile", 2, "Supplier profile"),
    ("country_sector", 3, "Country and sector risk"),
    ("company_risks", 4, "Company-specific risks found"),
    ("weighting", 5, "Weighting and prioritisation"),
    ("register", 6, "Risk register"),
    ("prevention", 7, "From priority risks to prevention"),
    ("documentation", 8, "Documentation"),
)
SECTION_IDS = tuple(s[0] for s in SECTIONS) + ("footer",)

NOT_FOUND = "Not found"
NOT_ASSESSED = "Not assessed"
BUYER_INPUT = "Buyer input, not assessed"
OWNER = "Assigned by buyer"
CHECKED_TEXT = "Checked, nothing adverse found"
NO_MEASURE = "To be agreed by the buyer."
DEFAULT_STEP = "Continue standard supplier qualification; this report is not a qualification."
CAP_STEPS = 3

BAFA_URL = ("https://www.bafa.de/SharedDocs/Downloads/DE/Lieferketten/handreichung_risikoanalyse.pdf"
            "?__blob=publicationFile&v=4")
BAFA_TITLE = "BAFA guide on identifying, weighting and prioritising supply chain risks (2022)"
FOOTER_TEXT = ("This report uses the structure of BAFA’s risk-analysis guide for all six risk areas. BAFA is the "
               "German authority that enforces the Supply Chain Due Diligence Act (LkSG). This report is not a "
               "legal LkSG risk analysis.")

AREA_STATUS_LABEL = {"red": "Red flag", "amber": "Watch item", "green": CHECKED_TEXT, "context": "Context only",
                     "not_assessed": NOT_ASSESSED}
PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("name", "Name"), ("description", "What the company does"), ("products", "Products or components"),
    ("headquarters", "Headquarters"), ("founded", "Founded"), ("parent_company", "Parent company"),
    ("sites", "Sites"), ("employees", "Employees"), ("employee_representation", "Employee representation"),
    ("order_volume", "Order volume"),
)
PROFILE_KEYS = frozenset(get_args(ProfileKey))
def intro_parts(r: ResearchResult) -> list[dict[str, Any]]:
    """The short company introduction for the TL;DR card, from the quote-checked profile only:
    what the company does (or its products) as a sentence, then short facts (HQ, founding year,
    parent) that the card joins with " · ".
    Each part keeps its source ids and quote for a citation; a field not found is left out."""
    p = r.profile
    parts: list[dict[str, Any]] = []

    def add(key: ProfileKey, text: str) -> None:
        pf = p[key]
        parts.append({"key": key, "text": text, "source_ids": list(pf.source_ids), "quote": pf.quote})

    if "description" in p:
        d = p["description"].value.rstrip(". ")
        add("description", d[:1].upper() + d[1:] + ".")
    elif "products" in p:
        add("products", "Products: " + p["products"].value.rstrip(". ") + ".")
    if "headquarters" in p:
        add("headquarters", "HQ " + p["headquarters"].value)
    if "founded" in p:
        add("founded", "Founded " + p["founded"].value)
    if "parent_company" in p:
        add("parent_company", "Part of " + p["parent_company"].value)
    return parts


METHOD_LINES = (
    "Each risk area gets a score from 0 to 100; higher means more risk. Bands: " + LEVEL_BANDS + ".",
    "Scores come from fixed rules that turn each verified fact into points, using published methods where they "
    "exist (credit ratings, the Altman Z-score, World Bank governance indicators). The total is a weighted average "
    "of the areas, with the weights of the challenge dataset.",
    "An area with no verified fact is “Not assessed”: it gets no score, never 0. With less than half of the score "
    "weight assessed, no total is shown.",
    "Two override rules apply: a current red flag from a trusted source puts its area at least at 50 (High), and a "
    "knock-out from a trusted source makes the total Critical.",
    "Flag colours are set by fixed rules, not by the AI. A fact found only on a site not in our trusted source list "
    "counts for less, is at most a watch item and is never a knock-out.",
)


def point_label(f: Flag) -> str:
    """Label of a headline point; strengths read "Checked, nothing adverse found"."""
    return CHECKED_TEXT if f.colour == "green" else COLOUR_WORD[f.colour]


def _tags(f: Flag) -> list[str]:
    tags = []
    if f.knockout:
        tags.append("knock-out")
    if f.claim_status == "alleged":
        tags.append("alleged")
    if f.company_stated:
        tags.append("company-stated")
    if f.stale:
        tags.append("older event")
    if f.trust == "unverified":
        tags.append(f"{UNVERIFIED_MARK} unverified source only" + (", capped at watch item" if f.capped_unverified
                                                                    else ""))
    return tags


_RULE_REF = re.compile(r"\s*\((?:[^()]|\([^()]*\))*(?:\.ya?ml|appendix|§)(?:[^()]|\([^()]*\))*\)")
_SRC_REF = re.compile(r"\s*\[(?:S\d+(?:,\s*)?)+\]")
_FILE_REF = re.compile(r";?\s*[\w./-]+\.ya?ml\b[^;]*")
_EVENT_RULE = re.compile(r";?\s*\b[a-z]+(?:_[a-z]+)+\s*->\s*(?:red|amber|green|neutral)\b")
_CODE_PAREN = re.compile(r"\s*\([a-z]+(?:_[a-z]+)+\)")


def plain_rule(text: str) -> str:
    """A scoring rule line without internal file names or document section numbers."""
    t = _RULE_REF.sub("", text or "")
    t = _SRC_REF.sub("", t)
    t = _FILE_REF.sub("", t)
    t = _EVENT_RULE.sub("", t)
    t = _CODE_PAREN.sub("", t)
    return " ".join(t.split()).strip(" ;,")


class _Builder:
    def __init__(self, r: ResearchResult, ev: Evidence, rule: HeatmapRule) -> None:
        self.r = r
        self.rule = rule
        self.idx = CitationIndex(r, ev, numbering="source")
        self.ranked = ranked_flags(r)
        self.flags_by_id = {f.id: f for f in r.flags}
        self.scores = area_scores(r)
        self.status: dict[str, AreaStatus] = {a.area: a for a in r.areas}
        adverse = [f for f in self.ranked if placed(f)]
        pos = {f.id: i for i, f in enumerate(adverse)}
        self.register_flags = sorted(adverse, key=lambda f: (self._prio(f), pos[f.id]))
        self.risk_id = {f.id: f"R{i}" for i, f in enumerate(self.register_flags, start=1)}
        self.measures_table = _measures_table()

    # -- helpers --------------------------------------------------------------
    def _prio(self, f: Flag) -> int:
        return self.rule.priority[severity_of(f, self.rule)][likelihood_of(f, self.rule)]

    def cite_flag(self, f: Flag) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.idx.for_flag(f)]

    def cite_sources(self, ids: list[str]) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.idx.for_sources(ids)]

    def flag_item(self, f: Flag) -> dict[str, Any]:
        return {"flag_id": f.id, "risk_id": self.risk_id.get(f.id), "colour": f.colour,
                "label": COLOUR_WORD[f.colour], "summary": f.summary, "date": f.event_date,
                "area": f.area, "area_label": AREA_LABELS[f.area], "tags": _tags(f), "quote": f.quote,
                "trust": f.trust, "cites": self.cite_flag(f)}

    def point_item(self, f: Flag) -> dict[str, Any]:
        """A headline point: the flag item, labelled like the TL;DR."""
        item = self.flag_item(f)
        item["label"] = point_label(f)
        return item

    def area_score(self, a: UmbrellaId) -> dict[str, Any]:
        s = self.scores[a]
        v = area_score_value(s)
        weight = self.r.scores.weights.get(a)
        return {"area": a, "label": AREA_LABELS[a], "score": v, "level": s.level if v is not None else None,
                "no_score": None if v is not None else no_score_label(self.r, s), "coverage": s.coverage,
                "trusted_pages": s.trusted_pages, "unverified_pages": s.unverified_pages,
                "weight_pct": round(weight * 100) if isinstance(weight, (int, float)) else None}

    def total(self) -> dict[str, Any]:
        rng = score_range(self.r)
        t = self.r.scores.total
        return {"score": t, "level": self.r.scores.total_level if t is not None else None,
                "shown": t is not None, "scored": is_scored(self.r),
                "text": score_line(self.r), "no_total": None if t is not None else (
                    NO_TOTAL_TEXT if is_scored(self.r) else "Not scored yet"),
                "coverage_pct": coverage_pct(self.r), "range": list(rng) if rng else None, "bands": LEVEL_BANDS}

    def measures(self, f: Flag) -> list[str]:
        out = []
        if f.knockout and self.measures_table.get("knockout"):
            out.append(str(self.measures_table["knockout"]))
        area = self.measures_table.get(f.area)
        if isinstance(area, Mapping) and area.get(f.colour):
            out.append(str(area[f.colour]))
        return out or [NO_MEASURE]

    # -- sections -------------------------------------------------------------
    def header(self) -> dict[str, Any]:
        r = self.r
        ent = r.entity
        st = r.stats
        checked = str(st.pages_read)
        if st.pages_read:
            checked += f" ({st.trusted_pages_read} trusted"
            checked += (f", {st.unverified_pages_read} {UNVERIFIED_TEXT})" if st.unverified_pages_read else ")")
        country = (ent.country_name or ent.country_code) if ent else (r.country_input or "")
        website = (ent.website if ent else "") or (r.website_input or "")
        fields = [
            {"key": "legal_entity", "label": "Legal entity", "value": ent.legal_name if ent else NOT_FOUND},
            {"key": "country", "label": "Country", "value": country or NOT_FOUND},
            {"key": "website", "label": "Website", "value": website or NOT_FOUND},
            {"key": "research_date", "label": "Research date", "value": r.researched_at[:10]},
            {"key": "sources_checked", "label": "Sources checked", "value": checked},
        ]
        searched = r.company_input if not ent or ent.legal_name.strip().lower() != r.company_input.strip().lower() \
            else None
        notices = [r.notice] if r.notice else []
        if r.status == "partial":
            notices.append("Partial result: the run stopped early (time or budget limit). Some areas may be "
                           "incomplete.")
        return {"company": company_name(r), "searched_as": searched, "fields": fields, "notices": notices,
                "status": r.status}

    def summary(self) -> dict[str, Any]:
        r = self.r
        tone = verdict_tone(r)
        out: dict[str, Any] = {"verdict": r.verdict, "tone": tone, "text": r.summary, "total": self.total(),
                               "areas": [self.area_score(a) for a in AREA_ORDER], "key_findings": [],
                               "no_findings": None, "not_assessed": [AREA_LABELS[a] for a in not_assessed_areas(r)],
                               "overrides": override_notes(r), "message": None}
        if r.status == "needs_clarification" and r.clarification:
            out["message"] = f"We need one detail before researching: {r.clarification.question}"
            return out
        if r.status == "error":
            out["message"] = "Research failed: " + ("; ".join(r.warnings) or "unknown error")
            return out
        points = key_points(r)
        out["key_findings"] = [self.point_item(f) for f in points]
        if not any(f.colour in ("red", "amber") for f in points):
            out["no_findings"] = "No red flags or watch items found in the sources checked."
        return out

    def profile(self) -> dict[str, Any]:
        r = self.r
        ent = r.entity
        evidence = [s.id for s in r.sources if ent and s.url in ent.evidence_urls]
        fields: list[dict[str, Any]] = []
        for key, label in PROFILE_FIELDS:
            if key == "order_volume":
                fields.append({"key": key, "label": label, "value": BUYER_INPUT, "state": "buyer_input",
                               "cites": []})
                continue
            pf = r.profile.get(cast(ProfileKey, key)) if key in PROFILE_KEYS else None
            if pf is not None:
                cites = self.idx.for_quote(pf.source_ids, pf.quote, f"profile:{key}")
                fields.append({"key": key, "label": label, "value": pf.value, "state": "found",
                               "cites": [c.to_dict() for c in cites]})
                continue
            value, ids = "", []
            if key == "name" and ent:
                value, ids = ent.legal_name, evidence
            elif key == "products" and "description" not in r.profile and ent and ent.description:
                value, ids = ent.description, evidence  # the identity line, only if nothing better was read
            fields.append({"key": key, "label": label, "value": value or NOT_FOUND,
                           "state": "found" if value else "not_found",
                           "cites": self.cite_sources(ids) if value else []})
        return {"fields": fields}

    def country_sector(self) -> dict[str, Any]:
        r = self.r
        country = (r.entity.country_name or r.entity.country_code) if r.entity else (r.country_input or "")
        indicators = []
        index_flags = [f for f in self.ranked if f.area == "country" and f.data and f.data.get("figures")]
        by_url = {s.url: s.id for s in r.sources}
        for f in index_flags:
            data = f.data or {}
            bands = data.get("band") or {}
            for fig in data.get("figures") or []:
                if not isinstance(fig, Mapping) or fig.get("value") is None:
                    continue
                val = f"{round(float(fig['value']))}/100"
                if fig.get("rank") and fig.get("of"):
                    val += f" (rank {fig['rank']} of {fig['of']})"
                sid = by_url.get(str(fig.get("source_url") or ""))
                band = bands.get(str(fig.get("indicator")))
                indicators.append({"label": str(fig.get("label") or fig.get("indicator")), "value": val,
                                   "year": fig.get("year"), "scale": str(fig.get("scale") or ""),
                                   "band": f"{band} risk" if band else "",
                                   "cites": self.cite_sources([sid]) if sid else self.cite_flag(f)})
        return {"country": country or NOT_FOUND, "area_score": self.area_score("country"),
                "indicators": indicators,
                "sector": {"label": "Sector risk", "value": NOT_ASSESSED,
                           "note": "No published sector risk index was checked for this supplier."}}

    def company_risks(self) -> dict[str, Any]:
        areas = []
        for a in AREA_ORDER:
            st = self.status.get(a)
            stat = st.status if st else "not_assessed"
            own = [f for f in self.ranked if f.area == a]
            if a == "country":
                own = [f for f in own if not (f.data and f.data.get("figures"))]
            order = {"red": 0, "amber": 1, "neutral": 2, "green": 3}
            rows = []
            for f in sorted(own, key=lambda x: order[x.colour]):  # stable: keeps the priority order inside
                item = self.flag_item(f)
                if f.colour in ("red", "amber"):
                    item["kind"] = "finding"
                elif f.colour == "green":
                    item["kind"], item["label"] = "checked", CHECKED_TEXT
                else:
                    item["kind"], item["label"] = "context", "Context"
                rows.append(item)
            if stat == "not_assessed" and not rows:
                note = "No verified facts from the sources checked."
                if st and st.unverified_pages_checked:
                    note += f" {UNVERIFIED_MARK} Pages from sites not in our trusted source list were read but gave " \
                            "nothing usable."
                rows.append({"kind": "not_assessed", "label": NOT_ASSESSED, "summary": note, "cites": []})
            elif a == "country" and not rows:
                rows.append({"kind": "pointer", "label": "Country indices",
                             "summary": "Country index figures are in section 3. No company-specific findings "
                                        "about locations were found.", "cites": []})
            areas.append({"area": a, "label": AREA_LABELS[a], "status": stat, "status_label": AREA_STATUS_LABEL[stat],
                          "score": self.area_score(a), "rows": rows})
        events, undated = timeline_events(self.r)
        timeline = {"events": [{"date": ev.flag.event_date, "area_label": AREA_LABELS[ev.flag.area],
                                "colour": ev.flag.colour, "label": COLOUR_WORD[ev.flag.colour],
                                "summary": ev.flag.summary, "flag_id": ev.flag.id} for ev in events],
                    "undated": undated}
        return {"areas": areas, "timeline": timeline}

    def weighting(self) -> dict[str, Any]:
        rule = self.rule
        cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for f in self.register_flags:
            key = (severity_of(f, rule), likelihood_of(f, rule))
            cells.setdefault(key, []).append({"risk_id": self.risk_id[f.id], "flag_id": f.id,
                                              "colour": f.colour, "summary": f.summary})
        rows = []
        for s in rule.severity_levels:
            row = []
            for li in rule.likelihood_levels:
                p = rule.priority[s][li]
                row.append({"likelihood": li, "label": rule.labels[li], "priority": p,
                            "priority_label": rule.priority_labels[p], "risks": cells.get((s, li), [])})
            rows.append({"severity": s, "label": rule.labels[s], "cells": row})
        return {"areas": [self.area_score(a) for a in AREA_ORDER], "total": self.total(),
                "heatmap": {"columns": [{"likelihood": li, "label": rule.labels[li]} for li in rule.likelihood_levels],
                            "rows": rows, "placed": len(self.register_flags)},
                "buyer_inputs": [
                    {"label": "Our influence on the supplier", "value": BUYER_INPUT},
                    {"label": "Our own contribution to the risk", "value": BUYER_INPUT},
                ]}

    def register(self) -> dict[str, Any]:
        rule = self.rule
        rows = []
        for f in self.register_flags:
            s, li = severity_of(f, rule), likelihood_of(f, rule)
            p = rule.priority[s][li]
            sc = self.area_score(f.area)
            rows.append({"risk_id": self.risk_id[f.id], "flag_id": f.id, "colour": f.colour,
                         "label": COLOUR_WORD[f.colour], "area_label": AREA_LABELS[f.area],
                         "description": f.summary, "date": f.event_date, "tags": _tags(f), "owner": OWNER,
                         "severity": rule.labels[s], "likelihood": rule.labels[li], "priority": p,
                         "priority_label": rule.priority_labels[p], "area_score": sc["score"],
                         "area_level": sc["level"], "area_no_score": sc["no_score"],
                         "measures": self.measures(f), "cites": self.cite_flag(f)})
        return {"rows": rows, "empty": None if rows else "No red flags or watch items to record."}

    def prevention(self) -> dict[str, Any]:
        steps_in = self.r.next_steps[:CAP_STEPS] or [DEFAULT_STEP]
        steps = []
        for text in steps_in:
            tied = [f for f in self.register_flags if text in self.measures(f)]
            steps.append({"text": text, "risks": [{"risk_id": self.risk_id[f.id], "flag_id": f.id,
                                                    "summary": f.summary} for f in tied]})
        return {"steps": steps}

    def documentation(self) -> dict[str, Any]:
        r = self.r
        weights = [{"label": AREA_LABELS[a], "pct": round(r.scores.weights[a] * 100)}
                   for a in AREA_ORDER if a in r.scores.weights]
        hm = describe(self.rule)
        breakdown = self._breakdown()
        followups = []
        for fu in r.followups:
            f = self.flags_by_id.get(fu.flag_id)
            followups.append({"question": fu.question, "flag_id": fu.flag_id,
                              "risk_id": self.risk_id.get(fu.flag_id), "on": COLOUR_WORD[f.colour] if f else None,
                              "outcome": fu.outcome or "No new information found.",
                              "cites": self.cite_sources(fu.corroborating_source_ids)})
        limits = list(r.limits) or ["Automated public-source research, not independent verification or supplier "
                                    "qualification."]
        # Sources last: their numbering includes every citation made above.
        sources = []
        for i, sid in enumerate(self.idx.order, start=1):
            s = self.idx.by_id[sid]
            if s.trust == "unverified":
                label = f"{UNVERIFIED_MARK} {UNVERIFIED_TEXT}"
            else:
                label = f"{TRUSTED_MARK} trusted" + (", company-stated" if s.tier == "company_own" else "")
            sources.append({"num": i, "source_id": sid, "trust": s.trust, "trust_label": label, "title": s.title,
                            "publisher": s.publisher, "published": normalize_date(s.published_date),
                            "accessed": s.retrieved_at[:10], "url": s.url,
                            "quotes": list(self.idx.quotes_by_source.get(sid, []))})
        return {"method": list(METHOD_LINES), "weights": weights,
                "total_method": plain_rule(r.scores.total_method) if r.scores.total_method else "",
                "heatmap_rule": {"severity": [list(x) for x in hm["severity"]],
                                 "likelihood": [list(x) for x in hm["likelihood"]],
                                 "note": "Severity comes from the flag colour; likelihood from how well the fact "
                                         "is verified. Only red flags and watch items are placed."},
                "breakdown": breakdown, "followups": followups, "limits": limits, "sources": sources,
                "uncited": len(r.sources) - len(self.idx.order)}

    def _line(self, c: Mapping[str, Any]) -> dict[str, Any]:
        ref = str(c.get("ref") or "")
        if ref in self.flags_by_id:
            prim: Citation | None = self.idx.primary(self.flags_by_id[ref])
            cites = [prim.to_dict()] if prim else []
        else:
            ids = [t for t in re.split(r"[\s,;]+", str(c.get("source") or "")) if t in self.idx.by_id]
            cites = self.cite_sources(ids)
        pts = c.get("points")
        return {"kind": str(c.get("kind") or ""), "label": str(c.get("label") or ""),
                "points": round(float(pts), 1) if isinstance(pts, (int, float)) else None,
                "rule": plain_rule(str(c.get("rule") or "")), "risk_id": self.risk_id.get(ref), "cites": cites}

    def _breakdown(self) -> dict[str, Any]:
        bd = self.r.scoring_detail
        if not isinstance(bd, Mapping) or not bd.get("areas"):
            return {"available": False, "areas": [], "total_overrides": [],
                    "note": "The per-fact breakdown was not saved with this result."}
        by_area = {str(a.get("area")): a for a in bd.get("areas") or [] if isinstance(a, Mapping)}
        areas = []
        for a in AREA_ORDER:
            ad = by_area.get(a)
            sc = self.area_score(a)
            if ad is None:
                areas.append({"area": a, "label": AREA_LABELS[a], "score": sc["score"], "level": sc["level"],
                              "no_score": sc["no_score"], "sub_scores": [], "overrides": []})
                continue
            subs = []
            for s in ad.get("sub_scores") or []:
                score = s.get("score")
                subs.append({"name": str(s.get("name") or ""), "label": _pretty(str(s.get("name") or "")),
                             "score": score, "level": s.get("level") if score is not None else None,
                             "weight_pct": _pct(s.get("weight")),
                             "not_assessed": None if score is not None else (
                                 plain_rule(str(s.get("not_assessed_reason") or "")) or NOT_ASSESSED),
                             "lines": [self._line(c) for c in s.get("contributions") or []]})
            areas.append({"area": a, "label": AREA_LABELS[a], "score": sc["score"], "level": sc["level"],
                          "no_score": sc["no_score"], "sub_scores": subs,
                          "overrides": [self._line(c) for c in ad.get("contributions") or []]})
        return {"available": True, "areas": areas,
                "total_overrides": [self._line(c) for c in bd.get("total_contributions") or []],
                "note": "Every fact that went into a score, with its points and the rule used."}


def _pretty(name: str) -> str:
    return name.removesuffix("_Score").replace("_", " ").capitalize()


def _pct(x: object) -> int | None:
    return round(float(x) * 100) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _measures_table() -> Mapping[str, Any]:
    """Suggested measures per area and colour: the next-step table in rules.yaml."""
    try:
        from .config import load_rules

        return load_rules().next_steps
    except Exception:  # noqa: BLE001  (a report must render even without the rule file)
        return {}


def build_sections(r: ResearchResult, ev: Evidence | None = None,
                   rule: HeatmapRule | None = None) -> list[dict[str, Any]]:
    b = _Builder(r, ev or Evidence(), rule or load_rule())
    out = []
    for sid, num, title in SECTIONS:
        body = getattr(b, sid)()
        out.append({"id": sid, "number": num, "title": title, **body})
    out.append({"id": "footer", "number": None, "title": "About this report", "text": FOOTER_TEXT,
                "link": BAFA_URL, "link_label": BAFA_TITLE})
    return out


def report_sections(result: ResultInput, page_texts: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """The report as an ordered list of plain dicts (JSON-serialisable), same order as the HTML report.

    Accepts a ResearchResult, a result.json dict or a path to result.json."""
    r, ev = load_input(result, page_texts)
    return build_sections(r, ev)


def section(sections: list[dict[str, Any]], sid: str) -> dict[str, Any]:
    return next(s for s in sections if s["id"] == sid)


__all__ = ["AREA_ORDER", "SECTION_IDS", "report_sections", "build_sections", "section", "plain_rule", "UMBRELLAS"]
