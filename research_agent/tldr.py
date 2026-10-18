"""Chatbot TL;DR and "How was this scored?" data, built only from result.json. Deterministic.

* :func:`tldr_data` -> dict for the chat UI: sentence segments, each with its citation numbers
  (NotebookLM-style), chips, and a citations table. Each citation carries the exact quote, a
  context excerpt with the quote's character offsets (when page text is available), and a
  text-fragment link (``url#:~:text=...``) that opens the source at the quoted passage.
* :func:`tldr` -> the same TL;DR as plain text with [n] markers, at most about 120 words: verdict, total, 3-5 cited points.
* :func:`score_explainer` -> data for the "How was this scored?" view, from the scoring
  step's per-fact breakdown if it is available, else from the ScoreCard alone.

A reference rendering of the chat panel is in ``templates/citation_demo.html``
(:func:`render_citation_demo` fills it with a result).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .models import Flag, ResearchResult
from .report_data import point_label
from .report_html import (
    AREA_LABELS,
    CitationIndex,
    Evidence,
    area_score_value,
    area_scores,
    company_name,
    coverage_pct,
    is_scored,
    load_input,
    not_assessed_areas,
    key_points,
    override_notes,
    score_line,
    score_range,
    verdict_tone,
)

MAX_WORDS = 120
FLAG_WORDS = (16, 12, 9, 7)  # summary word caps tried in turn until the TL;DR fits
TEMPLATE_DIR = Path(__file__).parent / "templates"
DEMO_TEMPLATE = TEMPLATE_DIR / "citation_demo.html"
_DATA_START, _DATA_END = "/*TLDR_DATA_START*/", "/*TLDR_DATA_END*/"
ResultInput = ResearchResult | Mapping[str, Any] | str | Path


def word_count(text: str) -> int:
    """Words a reader sees: URLs and [n] citation markers do not count."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\[\d+\]", "", text)
    return len([w for w in text.split() if re.search(r"\w", w)])


def _shorten(text: str, max_words: int) -> str:
    words = " ".join(text.split()).rstrip(".").split()
    return " ".join(words) if len(words) <= max_words else " ".join(words[:max_words]).rstrip(",;:") + "…"


def _sentence(text: str) -> str:
    t = " ".join(text.split()).rstrip()
    return t if not t or t[-1] in ".!?…" else t + "."


def _with_markers(text: str, nums: list[int]) -> str:
    if not nums:
        return text
    marks = "".join(f"[{n}]" for n in nums)
    if text.endswith((".", "!", "?")):
        return f"{text[:-1]} {marks}{text[-1]}"
    return f"{text} {marks}"


def _score_segment(r: ResearchResult) -> tuple[str, dict[str, Any]]:
    cov = coverage_pct(r)
    total, level = r.scores.total, r.scores.total_level
    text = score_line(r)  # same line as the report's summary section
    rng = score_range(r)
    return text, {"total": total, "level": level, "coverage_pct": cov, "scored": is_scored(r),
                  "range": list(rng) if rng else None, "text": text}


def _flag_text(f: Flag, max_words: int) -> str:
    when = f" ({f.event_date})" if f.event_date else ""
    tag = ", knock-out" if f.knockout else ""
    tag += ", alleged" if f.claim_status == "alleged" else ""
    tag += ", unverified source only" if f.trust == "unverified" else ""
    return _sentence(f"{point_label(f)}{tag}: {_shorten(f.summary, max_words)}{when}")


def _build(r: ResearchResult, ev: Evidence, report_url: str | None, max_words: int) -> dict[str, Any]:
    idx = CitationIndex(r, ev, numbering="passage")
    segments: list[dict[str, Any]] = []
    chips: list[dict[str, Any]] = []
    tone = verdict_tone(r)
    score: dict[str, Any] | None = None
    top: list[Flag] = []
    gaps: list[str] = []

    def seg(text: str, kind: str, cites: list[int] | None = None, **extra: Any) -> None:
        segments.append({"text": text, "kind": kind, "citations": cites or [], **extra})

    if r.status == "needs_clarification" and r.clarification:
        seg(_sentence(f"We need one detail before researching: {r.clarification.question}"), "clarification")
        chips.append({"kind": "verdict", "label": "Needs one detail", "tone": "neutral"})
    elif r.status == "error":
        seg(_sentence("Research failed: " + ("; ".join(r.warnings) or "unknown error")), "error")
        chips.append({"kind": "verdict", "label": "Research failed", "tone": "neutral"})
    else:
        verdict = r.verdict or "Research complete"
        if r.status == "partial":
            seg("Partial result (time or budget limit).", "partial")
        seg(_sentence(verdict), "verdict", tone=tone)
        chips.append({"kind": "verdict", "label": verdict, "tone": tone})
        score_text, score = _score_segment(r)
        seg(score_text, "score")
        chips.append({"kind": "score", "label": (f"{score['total']}/100 · {score['level']}"
                                                 if score["total"] is not None else "Not scored yet"
                                                 if not score["scored"] else "No total"),
                      "level": score["level"]})
        if score["coverage_pct"] is not None:
            chips.append({"kind": "coverage", "label": f"Coverage {score['coverage_pct']}%"})
        for note in override_notes(r):
            seg(note, "override")
        top = key_points(r)  # the same points, in the same order, as report section 1
        for f in top:
            c = idx.primary(f)
            nums = [c.num] if c else []
            seg(_flag_text(f, max_words), "flag", nums, colour=f.colour, flag_id=f.id, date=f.event_date,
                area=f.area, label=point_label(f))
            chips.append({"kind": "flag", "colour": f.colour, "label": _shorten(f.summary, 6),
                          "date": f.event_date, "area": AREA_LABELS[f.area], "citations": nums, "flag_id": f.id})
        if not any(f.colour in ("red", "amber") for f in top):
            seg("No red flags or watch items found in the sources checked.", "no_findings")
        gaps = [AREA_LABELS[a] for a in not_assessed_areas(r)]
        if gaps:
            seg(_sentence("Not assessed: " + ", ".join(gaps)), "gaps")
            chips += [{"kind": "not_assessed", "label": g} for g in gaps]
    pointer = f"Full report: {report_url}" if report_url else "Full report with all sources: see the report."
    seg(pointer, "pointer")
    text = " ".join(_with_markers(s["text"], s["citations"]) for s in segments)
    cites = [c.to_dict() for c in idx.all()]
    return {
        "status": r.status,
        "company": company_name(r),
        "researched_at": r.researched_at[:10],
        "verdict": {"text": r.verdict, "tone": tone},
        "score": score,
        "flags": [{"id": f.id, "colour": f.colour, "summary": f.summary, "date": f.event_date,
                   "area": AREA_LABELS[f.area]} for f in top],
        "not_assessed": gaps,
        "chips": chips,
        "segments": segments,
        "citations": cites,
        "report": {"url": report_url, "label": "Open full report"},
        "text": text,
        "word_count": word_count(text),
    }


def tldr_data(result: ResultInput, report_url: str | None = None,
              page_texts: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Structured TL;DR for the chat UI (segments + chips + citations), at most about 120 words."""
    r, ev = load_input(result, page_texts)
    out: dict[str, Any] = {}
    for cap in FLAG_WORDS:
        out = _build(r, ev, report_url, cap)
        if out["word_count"] <= MAX_WORDS:
            return out
    return out


def tldr(result: ResultInput, report_url: str | None = None, page_texts: Mapping[str, str] | None = None) -> str:
    """Plain-text TL;DR with [n] citation markers."""
    return str(tldr_data(result, report_url, page_texts)["text"])


# ---------------------------------------------------------------------------
# "How was this scored?"
# ---------------------------------------------------------------------------

_BREAKDOWN_KEYS = ("scoring", "score_detail", "scoring_report", "score_breakdown")


def _as_mapping(obj: object) -> Mapping[str, Any] | None:
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        data = dump()
        return data if isinstance(data, Mapping) else None
    return obj if isinstance(obj, Mapping) else None


def _pretty(name: str) -> str:
    return name.removesuffix("_Score").replace("_", " ").capitalize()


def _pct(x: object) -> int | None:
    return round(float(x) * 100) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def score_explainer(result: ResultInput, breakdown: object | None = None,
                    page_texts: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Data for the "How was this scored?" view.

    ``breakdown`` is the scoring step's per-fact report (``scoring.ScoringReport`` or its dict).
    If not given, it is looked up in the raw result under one of ``_BREAKDOWN_KEYS``. Without
    it, the view falls back to the ScoreCard (scores, levels, method lines) and says so."""
    raw: object = result
    if isinstance(result, (str, Path)):
        raw = json.loads(Path(result).read_text(encoding="utf-8"))
    r, ev = load_input(raw if isinstance(raw, Mapping) else result, page_texts)
    bd = _as_mapping(breakdown) if breakdown is not None else None
    if bd is None and isinstance(raw, Mapping):
        for key in _BREAKDOWN_KEYS:
            bd = _as_mapping(raw.get(key))
            if bd is not None:
                break
    idx = CitationIndex(r, ev, numbering="passage")
    flags = {f.id: f for f in r.flags}
    src_ids = {s.id for s in r.sources}

    def cites_for(ref: str, source: str) -> list[int]:
        if ref in flags:
            c = idx.primary(flags[ref])
            return [c.num] if c else []
        ids = [t for t in re.split(r"[\s,;]+", source or "") if t in src_ids]
        return [c.num for c in idx.for_sources(ids)]

    rng = score_range(r)
    total: dict[str, Any] = {"score": r.scores.total, "level": r.scores.total_level, "formula": r.scores.total_method,
             "coverage_pct": coverage_pct(r), "range": list(rng) if rng else None, "scored": is_scored(r)}
    areas: list[dict[str, Any]] = []
    if bd is not None:
        total["formula"] = str(bd.get("total_formula") or total["formula"])
        total["coverage_pct"] = _pct(bd.get("coverage")) if bd.get("coverage") is not None else total["coverage_pct"]
        if isinstance(bd.get("range_low"), int) and isinstance(bd.get("range_high"), int):
            total["range"] = [bd["range_low"], bd["range_high"]]
        total["confidence_pct"] = {str(k): _pct(v) for k, v in (bd.get("confidence_shares") or {}).items()}
        for a in bd.get("areas") or []:
            subs = []
            for s in a.get("sub_scores") or []:
                lines = [{"kind": c.get("kind"), "ref": c.get("ref"), "label": c.get("label"),
                          "points": c.get("points"), "rule": c.get("rule"),
                          "citations": cites_for(str(c.get("ref") or ""), str(c.get("source") or ""))}
                         for c in s.get("contributions") or []]
                subs.append({"name": s.get("name"), "label": _pretty(str(s.get("name") or "")),
                             "weight_pct": _pct(s.get("weight")), "score": s.get("score"), "level": s.get("level"),
                             "confidence": s.get("confidence"), "includes_unverified": bool(s.get("includes_unverified")),
                             "not_assessed_reason": s.get("not_assessed_reason") or "", "formula": s.get("formula") or "",
                             "lines": lines})
            area_id = a.get("area")
            areas.append({"area": area_id, "label": AREA_LABELS.get(area_id, str(a.get("label") or area_id)),
                          "score": a.get("score"), "level": a.get("level"), "weight_pct": _pct(a.get("weight")),
                          "coverage_pct": _pct(a.get("coverage_fraction")), "formula": a.get("formula") or "",
                          "sub_scores": subs})
    else:
        for a_id, s in area_scores(r).items():
            v = area_score_value(s)
            areas.append({"area": a_id, "label": AREA_LABELS[a_id], "score": v, "level": s.level if v is not None else None,
                          "weight_pct": _pct(r.scores.weights.get(a_id)), "coverage_pct": None, "formula": s.method,
                          "sub_scores": [{"name": n, "label": _pretty(n), "weight_pct": None, "score": sv,
                                          "level": None, "confidence": None, "includes_unverified": False,
                                          "not_assessed_reason": "", "formula": "", "lines": []}
                                         for n, sv in s.sub_scores.items()]})
    return {
        "available": bd is not None,
        "note": ("Per-fact breakdown from the scoring step." if bd is not None else
                 "The per-fact breakdown was not saved with this result; showing area scores and method lines only."),
        "method": "Published fact-to-number method (docs/research/facts-to-scores.md); weights from the challenge "
                  "dataset. Areas without evidence are Not assessed, never 0.",
        "total": total,
        "areas": areas,
        "citations": [c.to_dict() for c in idx.all()],
    }


# ---------------------------------------------------------------------------
# Reference chat UI
# ---------------------------------------------------------------------------


def _json_for_script(data: object) -> str:
    """JSON safe inside <script>: '<', '>' and '&' are escaped so page text cannot close the tag."""
    s = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1)
    return s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026") \
        .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def render_citation_demo(result: ResultInput, report_url: str | None = None,
                         page_texts: Mapping[str, str] | None = None, breakdown: object | None = None) -> str:
    """The reference chat-panel page (templates/citation_demo.html) filled with this result's TL;DR."""
    tpl = DEMO_TEMPLATE.read_text(encoding="utf-8")
    a, b = tpl.index(_DATA_START) + len(_DATA_START), tpl.index(_DATA_END)
    data = {"tldr": tldr_data(result, report_url, page_texts),
            "scoring": score_explainer(result, breakdown, page_texts)}
    return tpl[:a] + _json_for_script(data) + tpl[b:]
