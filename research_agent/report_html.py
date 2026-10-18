"""Deterministic HTML risk report rendered from a ResearchResult (or its result.json).

No model writes layout or wording here: the same result always gives the same bytes. Charts
are inline SVG or plain tables built by code (no JavaScript, no external assets), and the page
prints to A4.

The sections and their order follow BAFA's risk-analysis guide, used for all six risk areas
(docs/research/report-template-standard.md): 0 header, 1 summary for decision makers,
2 supplier profile, 3 country and sector risk, 4 company-specific risks found, 5 weighting and
prioritisation (area scores, radar, likelihood x severity heatmap), 6 risk register, 7 from
priority risks to prevention, 8 documentation, then a footer. The section data comes from
report_data.py (:func:`report_sections`), which the web app can render in the same order.

Usage: ``python -m research_agent.report_html path/to/result.json [-o report.html]``.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

from .dates import normalize_date, parse_date
from .models import UMBRELLAS, AreaScore, Flag, ResearchResult, Source, UmbrellaId
from .rules import sort_flags

# ---------------------------------------------------------------------------
# Fixed vocabulary
# ---------------------------------------------------------------------------

# Umbrella names of the challenge dataset (config/scoring.yaml, "dataset_umbrella"); a test
# keeps the two in step. Order = models.UMBRELLAS = the teammate's app radar order.
AREA_LABELS: dict[UmbrellaId, str] = {
    "financial": "Financial",
    "legal": "Legal & Governance",
    "country": "Country & Location",
    "people": "People & Safety",
    "operations": "Operations & Delivery",
    "reputation": "Reputation & Outside View",
}
RADAR_LABELS: dict[UmbrellaId, str] = {
    "financial": "Financial", "legal": "Legal", "country": "Country",
    "people": "People & Safety", "operations": "Operations", "reputation": "Reputation",
}
LEVEL_BANDS = "Low 0–24 · Medium 25–49 · High 50–74 · Critical 75–100"

# Status colours (fixed; always shown with a shape and a word, never colour alone).
COLOUR_HEX = {"red": "#d03b3b", "amber": "#fab219", "green": "#0ca30c", "neutral": "#87949c"}
COLOUR_STROKE = {"red": "#9e2626", "amber": "#a87100", "green": "#077307", "neutral": "#56656f"}
COLOUR_GLYPH = {"red": "◆", "amber": "▲", "green": "●", "neutral": "○"}
COLOUR_WORD = {"red": "Red flag", "amber": "Watch item", "green": "Strength", "neutral": "Context"}
LEVEL_COLOUR = {"Low": "green", "Medium": "amber", "High": "serious", "Critical": "red"}
LEVEL_HEX = {"Low": "#0ca30c", "Medium": "#fab219", "High": "#ec835a", "Critical": "#d03b3b"}
TEAL = "#0f6e74"
RING = "#dce2e6"
MUTED = "#87949c"
INK2 = "#56656f"

TRUSTED_MARK = "✅"
UNVERIFIED_MARK = "🟨"
UNVERIFIED_TEXT = "not in our trusted source list"

def e(text: object) -> str:
    """HTML-escape any text that came from a page, a model or a user."""
    return html.escape(" ".join(str(text).split()), quote=True)


def _ex(text: str) -> str:
    """Escape an excerpt piece, keeping its edge spaces (it sits next to a <mark>)."""
    return html.escape(re.sub(r"\s+", " ", text), quote=True)


def _num(x: float) -> str:
    """Fixed float formatting so SVG output is byte-stable."""
    s = f"{x:.1f}"
    return "0.0" if s == "-0.0" else s


def safe_url(url: str) -> str | None:
    """Only http(s) links become hrefs; anything else (javascript:, data:) is shown as text."""
    try:
        p = urlparse(url.strip())
    except ValueError:
        return None
    return url.strip() if p.scheme in ("http", "https") and p.netloc else None


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


# ---------------------------------------------------------------------------
# View helpers shared with tldr.py
# ---------------------------------------------------------------------------


def as_result(result: ResearchResult | Mapping[str, Any] | str | Path) -> ResearchResult:
    """Accept a ResearchResult, a result.json dict, or a path to result.json."""
    if isinstance(result, ResearchResult):
        return result
    if isinstance(result, (str, Path)):
        return ResearchResult.model_validate_json(Path(result).read_text(encoding="utf-8"))
    return ResearchResult.model_validate(dict(result))


def company_name(r: ResearchResult) -> str:
    return r.entity.legal_name if r.entity else r.company_input


def area_scores(r: ResearchResult) -> dict[UmbrellaId, AreaScore]:
    by = {a.area: a for a in r.scores.areas}
    status = {a.area: a for a in r.areas}
    out: dict[UmbrellaId, AreaScore] = {}
    for a in UMBRELLAS:
        if a in by:
            out[a] = by[a]
        else:  # result without a ScoreCard row: derive coverage from the area status
            st = status.get(a)
            cov = ("assessed" if st and st.trusted_pages_used else
                   "unverified_only" if st and st.unverified_pages_used else "not_assessed")
            out[a] = AreaScore(area=a, coverage=cov, trusted_pages=st.trusted_pages_used if st else 0,
                               unverified_pages=st.unverified_pages_used if st else 0)
    return out


def area_score_value(s: AreaScore) -> int | None:
    """An area's score, or None. A not-assessed area never has one, whatever the input says."""
    return None if s.coverage == "not_assessed" else s.score


def is_scored(r: ResearchResult) -> bool:
    return r.scores.total is not None or any(area_score_value(s) is not None for s in area_scores(r).values())


def coverage_pct(r: ResearchResult) -> int | None:
    """Share of the score weight that has evidence (facts-to-scores §A5: c = Σ assessed w).

    Uses a ``coverage`` number on the ScoreCard if scoring provides one; otherwise the scored
    areas when scores exist, else the areas with any evidence. None when weights are unknown."""
    given = getattr(r.scores, "coverage", None)
    if isinstance(given, (int, float)) and not isinstance(given, bool):
        return round(given * 100) if given <= 1 else round(given)
    m = _COV_RE.search(r.scores.total_method or "")
    if m:  # the scoring step states sub-score coverage in its method line
        return round(float(m.group(1)))
    weights = r.scores.weights
    total_w = sum(weights.get(a, 0.0) for a in UMBRELLAS)
    if total_w <= 0:
        return None
    scores = area_scores(r)
    scored = is_scored(r)
    covered = sum(weights.get(a, 0.0) for a, s in scores.items()
                  if (area_score_value(s) is not None if scored else s.coverage != "not_assessed"))
    return round(100 * covered / total_w)


def no_score_label(r: ResearchResult, s: AreaScore) -> str:
    """Why an area has no number: "Not assessed" (no evidence, or scoring found nothing to score)
    or "not scored yet" (the scoring step has not run)."""
    return "Not assessed" if s.coverage == "not_assessed" or is_scored(r) else "not scored yet"


def not_assessed_areas(r: ResearchResult) -> list[UmbrellaId]:
    """Areas without a score that are not just waiting for the scoring step."""
    return [a for a, s in area_scores(r).items()
            if area_score_value(s) is None and no_score_label(r, s) == "Not assessed"]


_COV_RE = re.compile(r"coverage (\d+(?:\.\d+)?) ?%")
_RANGE_RE = re.compile(r"(?:0 or 100|possible range):? (\d+)\s*[-–]\s*(\d+)")


def score_range(r: ResearchResult) -> tuple[int, int] | None:
    """Best/worst total if the missing scores were 0 or 100 (appendix §A5), when scoring gives it."""
    lo, hi = getattr(r.scores, "range_low", None), getattr(r.scores, "range_high", None)
    if isinstance(lo, int) and isinstance(hi, int):
        return lo, hi
    m = _RANGE_RE.search(r.scores.total_method or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def ranked_flags(r: ResearchResult) -> list[Flag]:
    return sort_flags(r.flags)


MIN_POINTS, MAX_POINTS, MAX_ADVERSE_POINTS = 3, 5, 4


def key_points(r: ResearchResult) -> list[Flag]:
    """The headline findings shared by the report summary and the chat TL;DR.

    Red flags, then watch items, then strengths ("checked, nothing adverse found"), most serious
    first within each. At most four red flags and watch items, then strengths until there are
    at least three points, or one strength if there is room; five points at most. Only flags
    that cite a known source are used, so every point has a citation."""
    known = {s.id for s in r.sources}
    cited = [f for f in ranked_flags(r) if any(sid in known for sid in f.source_ids)]
    adverse = [f for f in cited if f.colour == "red"] + [f for f in cited if f.colour == "amber"]
    adverse = adverse[:MAX_ADVERSE_POINTS]
    greens = [f for f in cited if f.colour == "green"]
    n_green = max(MIN_POINTS - len(adverse), 1 if greens else 0)
    return (adverse + greens[:n_green])[:MAX_POINTS]


def verdict_tone(r: ResearchResult) -> str:
    """Banner colour: critical (knock-out), red, amber, green, or neutral (not enough evidence)."""
    if r.status in ("error", "needs_clarification"):
        return "neutral"
    if any(f.knockout for f in r.flags):
        return "critical"
    if any(f.colour == "red" for f in r.flags):
        return "red"
    if any(f.colour == "amber" for f in r.flags):
        return "amber"
    if r.stats.trusted_pages_read == 0 or all(s.coverage == "not_assessed" for s in area_scores(r).values()):
        return "neutral"
    return "green"


NO_TOTAL_TEXT = "No total: too little assessed"


def score_line(r: ResearchResult) -> str:
    """The one-line total used by the report summary and the chat TL;DR (kept identical)."""
    cov = coverage_pct(r)
    total, level = r.scores.total, r.scores.total_level
    if total is not None:
        return f"Risk score {total}/100 · {level}" + (f" · coverage {cov}%." if cov is not None else ".")
    if is_scored(r):
        return NO_TOTAL_TEXT + (f" (coverage {cov}%)." if cov is not None else ".")
    return "Risk score not scored yet" + (f"; evidence covers {cov}% of the score weight." if cov is not None
                                          else ".")


_RAISED = re.compile(r"raised to (\d+)")


def override_notes(r: ResearchResult) -> list[str]:
    """Plain sentences for the override rules that changed a score (area floor, knock-out),
    read from the scoring breakdown. Shared by the report summary and the chat TL;DR."""
    bd = r.scoring_detail
    if not isinstance(bd, Mapping):
        return []
    notes: list[str] = []
    for a in bd.get("areas") or []:
        if not isinstance(a, Mapping) or a.get("area") not in AREA_LABELS:
            continue
        for c in a.get("contributions") or []:
            m = _RAISED.search(str(c.get("label") or "")) if isinstance(c, Mapping) else None
            if m and c.get("kind") == "override":
                notes.append(f"{AREA_LABELS[a['area']]} raised to {m.group(1)} (High) by a current red flag "
                             "from a trusted source.")
    for c in bd.get("total_contributions") or []:
        m = _RAISED.search(str(c.get("label") or "")) if isinstance(c, Mapping) else None
        if m and c.get("kind") == "override":
            notes.append(f"Total raised to {m.group(1)} (Critical) by a knock-out finding from a trusted source.")
    return notes


def score_text(score: int | None, level: str | None) -> str:
    return f"{score}/100 · {level}" if score is not None and level else (
        f"{score}/100" if score is not None else "not scored yet")


# ---------------------------------------------------------------------------
# Citations (NotebookLM-style: every [n] points to the exact quoted passage)
# ---------------------------------------------------------------------------

CONTEXT_CHARS = 200
_ELLIPSIS = re.compile(r"\s*(?:\.\.\.|…|\[\.\.\.\])\s*")
_WORD = re.compile(r"\w+")
TRUST_LABEL = {"trusted": f"{TRUSTED_MARK} trusted", "company_stated": f"{TRUSTED_MARK} trusted, company-stated",
               "unverified": f"{UNVERIFIED_MARK} {UNVERIFIED_TEXT}"}


@dataclass
class Evidence:
    """Optional page text for citation context. result.json does not store page text today;
    the orchestrator can pass ``page_texts`` (source id -> text) or store a per-flag
    ``quote_context`` (the quote ± ~200 characters); both are read here if present."""

    page_texts: dict[str, str] = field(default_factory=dict)
    quote_contexts: dict[str, str] = field(default_factory=dict)


def _extract_evidence(raw: object, page_texts: Mapping[str, str] | None) -> Evidence:
    ev = Evidence(page_texts=dict(page_texts or {}))
    data: Mapping[str, Any] | None = None
    if isinstance(raw, Mapping):
        data = raw
    elif isinstance(raw, ResearchResult):
        data = None
    if data is not None:
        for s in data.get("sources") or []:
            if isinstance(s, Mapping):
                for key in ("page_text", "text", "text_excerpt"):
                    t = s.get(key)
                    if isinstance(t, str) and t and str(s.get("id")) not in ev.page_texts:
                        ev.page_texts[str(s.get("id"))] = t
        for f in data.get("flags") or []:
            if isinstance(f, Mapping) and isinstance(f.get("quote_context"), str) and f.get("quote_context"):
                ev.quote_contexts[str(f.get("id"))] = str(f["quote_context"])
    if isinstance(raw, ResearchResult):
        for f in raw.flags:
            qc = getattr(f, "quote_context", None)
            if isinstance(qc, str) and qc:
                ev.quote_contexts[f.id] = qc
    return ev


def locate_quote(quote: str, text: str) -> tuple[int, int] | None:
    """Character span of ``quote`` inside ``text``, matching word by word and ignoring case,
    whitespace and punctuation (as the quote check does). Quotes with '...' match in order."""
    words = [(m.group().casefold(), m.start(), m.end()) for m in _WORD.finditer(text)]
    tokens = [w for w, _, _ in words]
    pos, first, last = 0, -1, -1
    for part in (p for p in _ELLIPSIS.split(quote) if p.strip()):
        needle = [w.casefold() for w in _WORD.findall(part)]
        if not needle:
            continue
        found = -1
        for i in range(pos, len(tokens) - len(needle) + 1):
            if tokens[i:i + len(needle)] == needle:
                found = i
                break
        if found < 0:
            return None
        if first < 0:
            first = found
        last = found + len(needle) - 1
        pos = last + 1
    if first < 0:
        return None
    return words[first][1], words[last][2]


def excerpt_around(text: str, start: int, end: int, pad: int = CONTEXT_CHARS) -> tuple[str, int, int]:
    """The quote ± ``pad`` characters, cut at word boundaries, with the quote's offsets inside."""
    a, b = max(0, start - pad), min(len(text), end + pad)
    if a > 0:
        sp = text.find(" ", a, start)
        a = sp + 1 if sp >= 0 else a
    if b < len(text):
        sp = text.rfind(" ", end, b)
        b = sp if sp >= 0 else b
    prefix = "… " if a > 0 else ""
    suffix = " …" if b < len(text) else ""
    body = re.sub(r"[\r\n\t\f\v]", " ", text[a:b])
    return prefix + body + suffix, len(prefix) + start - a, len(prefix) + end - a


def _frag(s: str) -> str:
    # Text fragments must percent-encode '-', ',' and '&' as well; quote(safe="") leaves '-'.
    return quote(s, safe="").replace("-", "%2D")


def text_fragment_url(url: str, quote_text: str, max_exact_words: int = 8, edge_words: int = 4) -> str:
    """``url#:~:text=start,end`` so supporting browsers scroll to and highlight the quote.
    Short quotes are matched exactly; long ones by their first and last words."""
    base = safe_url(url)
    if base is None:
        return url
    parts = [p for p in _ELLIPSIS.split(quote_text) if p.strip()]
    if not parts:
        return base
    first, last = parts[0].split(), parts[-1].split()
    if len(parts) == 1 and len(first) <= max_exact_words:
        spec = _frag(" ".join(first))
    else:
        spec = _frag(" ".join(first[:edge_words])) + "," + _frag(" ".join(last[-edge_words:]))
    return base.split("#", 1)[0] + "#:~:text=" + spec


@dataclass(frozen=True)
class Citation:
    """One cited passage: a source, and for a flag's primary source the exact quote."""

    num: int
    source_id: str
    flag_id: str | None
    url: str
    link: str
    title: str
    publisher: str
    published: str | None
    accessed: str
    trust: str
    trust_label: str
    quote: str
    excerpt: str
    quote_start: int
    quote_end: int
    context_found: bool

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.num, "source_id": self.source_id, "flag_id": self.flag_id, "url": self.url,
                "link": self.link, "title": self.title, "publisher": self.publisher,
                "published": self.published, "accessed": self.accessed, "trust": self.trust,
                "trust_label": self.trust_label, "quote": self.quote, "excerpt": self.excerpt,
                "quote_start": self.quote_start, "quote_end": self.quote_end,
                "context_found": self.context_found}


def source_trust(s: Source) -> str:
    return "unverified" if s.trust == "unverified" else "company_stated" if s.tier == "company_own" else "trusted"


class CitationIndex:
    """Builds and numbers citations in order of first use.

    ``numbering="source"``: one number per source (the report; matches its Sources list).
    ``numbering="passage"``: one number per quoted passage (the chatbot TL;DR)."""

    def __init__(self, r: ResearchResult, evidence: Evidence | None = None,
                 numbering: str = "source") -> None:
        self.by_id = {s.id: s for s in r.sources}
        self.ev = evidence or Evidence()
        self.numbering = numbering
        self.order: list[str] = []  # source ids, first use first
        self._keys: list[tuple[str, str | None]] = []
        self._made: dict[tuple[str, str | None], Citation] = {}
        self.quotes_by_source: dict[str, list[str]] = {}

    def primary_source(self, f: Flag) -> str | None:
        """The source the quote was copied from: one whose page text holds it, else the first."""
        ids = [s for s in f.source_ids if s in self.by_id]
        for sid in ids:
            t = self.ev.page_texts.get(sid)
            if t and locate_quote(f.quote, t):
                return sid
        return ids[0] if ids else None

    def _get(self, sid: str, f: Flag | None) -> Citation:
        key = (sid, f.id if f else None)
        if key in self._made:
            return self._made[key]
        if sid not in self.order:
            self.order.append(sid)
        self._keys.append(key)
        num = self.order.index(sid) + 1 if self.numbering == "source" else len(self._keys)
        s = self.by_id[sid]
        q = " ".join(f.quote.split()) if f else ""
        excerpt, qs, qe, found = q, 0, len(q), False
        texts = [self.ev.quote_contexts.get(f.id, "") if f else "", self.ev.page_texts.get(sid, "")]
        for t in texts:
            span = locate_quote(q, t) if q and t else None
            if span:
                excerpt, qs, qe = excerpt_around(t, span[0], span[1])
                found = True
                break
        if q:
            self.quotes_by_source.setdefault(sid, [])
            if q not in self.quotes_by_source[sid]:
                self.quotes_by_source[sid].append(q)
        url = s.url.strip()
        trust = source_trust(s)
        c = Citation(num=num, source_id=sid, flag_id=f.id if f else None, url=url,
                     link=text_fragment_url(url, q) if q else (safe_url(url) or url), title=s.title,
                     publisher=s.publisher, published=normalize_date(s.published_date),
                     accessed=s.retrieved_at[:10], trust=trust, trust_label=TRUST_LABEL[trust], quote=q,
                     excerpt=excerpt, quote_start=qs, quote_end=qe, context_found=found)
        self._made[key] = c
        return c

    def for_flag(self, f: Flag) -> list[Citation]:
        """Primary source (with the quote) first, then corroborating sources (no quote)."""
        prim = self.primary_source(f)
        out = [self._get(prim, f)] if prim else []
        out += [self._get(sid, None) for sid in f.source_ids if sid in self.by_id and sid != prim]
        return out

    def primary(self, f: Flag) -> Citation | None:
        """Only the citation carrying the flag's quote."""
        prim = self.primary_source(f)
        return self._get(prim, f) if prim else None

    def for_sources(self, source_ids: list[str]) -> list[Citation]:
        seen: list[str] = []
        for sid in source_ids:
            if sid in self.by_id and sid not in seen:
                seen.append(sid)
        return [self._get(sid, None) for sid in seen]

    def all(self) -> list[Citation]:
        return [self._made[k] for k in self._keys]


class _Cites(CitationIndex):
    """Report citations: [n] links with a pure-CSS popover showing the quote in context."""

    def __init__(self, r: ResearchResult, evidence: Evidence | None = None) -> None:
        super().__init__(r, evidence, numbering="source")
        self._pop = 0

    def _chip(self, c: Citation) -> str:
        self._pop += 1
        pid = f"cp-{self._pop}"
        mark = UNVERIFIED_MARK if c.trust == "unverified" else ""
        href = safe_url(c.link.split("#", 1)[0])
        link = e(c.link) if href else ""
        badge = f'<span class="badge {c.trust}">{e(c.trust_label)}</span>'
        if c.quote:
            q = (f'{_ex(c.excerpt[:c.quote_start])}<mark>{_ex(c.excerpt[c.quote_start:c.quote_end])}</mark>'
                 f'{_ex(c.excerpt[c.quote_end:])}')
            ctx = "" if c.context_found else '<span class="pop-n">Quote as stored; page context not saved.</span>'
            body = f'<span class="pop-q">{q}</span>{ctx}'
        else:
            body = '<span class="pop-n">Corroborating source for this point; no quote stored from it.</span>'
        open_link = (f'<a class="pop-a" href="{link}" rel="noopener noreferrer">Open source at this passage</a>'
                     if c.quote and href else
                     f'<a class="pop-a" href="{link}" rel="noopener noreferrer">Open source</a>' if href else "")
        pop = (f'<span class="pop" role="tooltip" id="{pid}"><span class="pop-h">{e(c.publisher)} · '
               f'{e(c.published or "date not stated")} {badge}</span><span class="pop-t">{e(c.title)}</span>'
               f'{body}{open_link}</span>')
        label = f"[{c.num}]{mark}"
        anchor = (f'<a class="cite" href="{link}" aria-describedby="{pid}" rel="noopener noreferrer">{label}</a>'
                  if href else f'<span class="cite" tabindex="0" aria-describedby="{pid}">{label}</span>')
        return f'<span class="cw">{anchor}{pop}</span>'

    def cite_flag(self, f: Flag) -> str:
        return " ".join(self._chip(c) for c in self.for_flag(f))

    def cite(self, source_ids: list[str]) -> str:
        return " ".join(self._chip(c) for c in self.for_sources(source_ids))


# ---------------------------------------------------------------------------
# SVG charts
# ---------------------------------------------------------------------------

_RCX, _RCY, _RR = 220.0, 138.0, 88.0


def _rpt(i: int, v: float) -> tuple[float, float]:
    ang = i * math.pi / 3
    return _RCX + math.sin(ang) * _RR * v / 100, _RCY - math.cos(ang) * _RR * v / 100


def _poly(vals: list[float]) -> str:
    return " ".join(f"{_num(x)},{_num(y)}" for x, y in (_rpt(i, v) for i, v in enumerate(vals)))


def radar_svg(r: ResearchResult) -> str:
    """6-axis radar of the area scores, styled like the app radar (teal polygon, grey rings).

    A scored axis gets a teal vertex. An axis without a score is never plotted: its spoke is
    dashed grey, it ends in a hollow marker and its label says why ("Not assessed" or
    "not scored yet"). With no scores at all the chart is a labelled placeholder."""
    scores = area_scores(r)
    vals: list[int | None] = [area_score_value(scores[a]) for a in UMBRELLAS]
    scored_n = sum(v is not None for v in vals)
    desc_parts = []
    for a, v in zip(UMBRELLAS, vals):
        s = scores[a]
        desc_parts.append(f"{AREA_LABELS[a]} {v} {s.level or ''}".strip() if v is not None else
                          f"{AREA_LABELS[a]} {no_score_label(r, s).lower()}")
    label = ("Risk profile by area, 0 to 100, higher means more risk. " + "; ".join(desc_parts) + ".")
    out = [f'<svg class="radar" viewBox="0 0 440 276" role="img" aria-labelledby="radar-title" '
           f'xmlns="http://www.w3.org/2000/svg"><title id="radar-title">{e(label)}</title>']
    for n in (25, 50, 75, 100):
        out.append(f'<polygon points="{_poly([n] * 6)}" fill="none" stroke="{RING}"/>')
    for i, a in enumerate(UMBRELLAS):
        x, y = _rpt(i, 100)
        dashed = ' stroke-dasharray="3 3"' if vals[i] is None else ""
        out.append(f'<line x1="{_num(_RCX)}" y1="{_num(_RCY)}" x2="{_num(x)}" y2="{_num(y)}" stroke="{RING}"{dashed}/>')
    out.append(f'<text x="{_num(_RCX + 4)}" y="{_num(_RCY - _RR - 3)}" font-size="9" fill="{MUTED}">100</text>')
    out.append(f'<text x="{_num(_RCX + 4)}" y="{_num(_RCY - _RR / 2 - 2)}" font-size="9" fill="{MUTED}">50</text>')
    if scored_n == 6:
        out.append(f'<polygon class="profile" points="{_poly([float(v or 0) for v in vals])}" '
                   f'fill="{TEAL}25" stroke="{TEAL}" stroke-width="2"/>')
    elif scored_n >= 2:
        # Join only neighbouring scored axes; a gap stays open instead of dropping to 0.
        for i in range(6):
            j = (i + 1) % 6
            vi, vj = vals[i], vals[j]
            if vi is not None and vj is not None:
                (x1, y1), (x2, y2) = _rpt(i, vi), _rpt(j, vj)
                out.append(f'<line class="profile-edge" x1="{_num(x1)}" y1="{_num(y1)}" x2="{_num(x2)}" '
                           f'y2="{_num(y2)}" stroke="{TEAL}" stroke-width="2"/>')
    for i, a in enumerate(UMBRELLAS):
        v = vals[i]
        s = scores[a]
        if v is not None:
            x, y = _rpt(i, v)
            out.append(f'<circle class="vertex" data-axis="{a}" data-value="{v}" cx="{_num(x)}" cy="{_num(y)}" '
                       f'r="4" fill="{TEAL}"><title>{e(AREA_LABELS[a])}: {v} {e(s.level or "")}</title></circle>')
        else:
            x, y = _rpt(i, 100)
            why = no_score_label(r, s)
            out.append(f'<circle class="vertex na" data-axis="{a}" data-value="none" cx="{_num(x)}" cy="{_num(y)}" '
                       f'r="4.5" fill="#ffffff" stroke="{MUTED}" stroke-width="1.5"><title>{e(AREA_LABELS[a])}: '
                       f'{why}</title></circle>')
    for i, a in enumerate(UMBRELLAS):
        v = vals[i]
        s = scores[a]
        x, y = _rpt(i, 128)
        anchor = "start" if i in (1, 2) else "end" if i in (4, 5) else "middle"
        y1 = y - 14 if i == 0 else y if i == 3 else y - 6
        if v is not None:
            sub, colour, style = f"{v} · {s.level or '—'}", "#1d2a31", ""
        else:
            sub, colour, style = no_score_label(r, s), MUTED, ' font-style="italic"'
        name_fill = "#1d2a31" if v is not None else INK2
        out.append(f'<text x="{_num(x)}" y="{_num(y1)}" text-anchor="{anchor}" font-size="12" fill="{name_fill}">'
                   f'{e(RADAR_LABELS[a])}</text>')
        out.append(f'<text x="{_num(x)}" y="{_num(y1 + 13)}" text-anchor="{anchor}" font-size="11" '
                   f'fill="{colour}"{style}>{e(sub)}</text>')
    if scored_n == 0:
        out.append(f'<rect x="{_num(_RCX - 58)}" y="{_num(_RCY - 17)}" width="116" height="34" rx="3" '
                   f'fill="#ffffff" fill-opacity="0.9"/>')
        out.append(f'<text x="{_num(_RCX)}" y="{_num(_RCY - 4)}" text-anchor="middle" font-size="12" '
                   f'fill="{INK2}">Not scored yet</text>')
        out.append(f'<text x="{_num(_RCX)}" y="{_num(_RCY + 11)}" text-anchor="middle" font-size="9.5" '
                   f'fill="{MUTED}">scale shown for reference</text>')
    out.append("</svg>")
    return "".join(out)


def _shape(colour: str, x: float, y: float, title: str) -> str:
    fill, stroke = COLOUR_HEX[colour], COLOUR_STROKE[colour]
    t = f"<title>{title}</title>"
    if colour == "red":
        pts = f"{_num(x)},{_num(y - 6)} {_num(x + 6)},{_num(y)} {_num(x)},{_num(y + 6)} {_num(x - 6)},{_num(y)}"
        return f'<polygon class="ev ev-red" points="{pts}" fill="{fill}" stroke="{stroke}">{t}</polygon>'
    if colour == "amber":
        pts = f"{_num(x)},{_num(y - 6)} {_num(x + 6)},{_num(y + 5)} {_num(x - 6)},{_num(y + 5)}"
        return f'<polygon class="ev ev-amber" points="{pts}" fill="{fill}" stroke="{stroke}">{t}</polygon>'
    return (f'<circle class="ev ev-{colour}" cx="{_num(x)}" cy="{_num(y)}" r="5" fill="{fill}" '
            f'stroke="{stroke}">{t}</circle>')


@dataclass(frozen=True)
class _Event:
    flag: Flag
    when: date


def timeline_events(r: ResearchResult) -> tuple[list[_Event], int]:
    """Dated red/amber/green flags (oldest first) and the number of undated ones left out."""
    events: list[_Event] = []
    undated = 0
    for f in r.flags:
        if f.colour == "neutral":
            continue
        d = parse_date(f.event_date)
        if d is None:
            undated += 1
        else:
            events.append(_Event(f, d))
    events.sort(key=lambda ev: (ev.when, UMBRELLAS.index(ev.flag.area), ev.flag.id))
    return events, undated


def timeline_svg(r: ResearchResult) -> str:
    """Dated flags by area (rows) and time (x), coloured and shaped by flag colour."""
    events, _ = timeline_events(r)
    today = parse_date(r.researched_at[:10]) or (max(ev.when for ev in events) if events else date(2000, 1, 1))
    first = min([ev.when for ev in events] + [today])
    y0, y1 = first.year, max(today.year, max((ev.when.year for ev in events), default=today.year)) + 1
    start, end = date(y0, 1, 1), date(y1, 1, 1)
    left, right, top, row_h, width = 150.0, 664.0, 8.0, 22.0, 680.0
    span = (end - start).days or 1

    def x_of(d: date) -> float:
        return left + (right - left) * (d - start).days / span

    height = top + row_h * 6 + 26
    desc = (f"Timeline of {plural(len(events), 'dated finding')} from {y0} to {today.isoformat()}, by area. "
            "Red flags are diamonds, watch items triangles, strengths circles.")
    out = [f'<svg class="timeline" viewBox="0 0 {_num(width)} {_num(height)}" role="img" '
           f'aria-labelledby="tl-title" xmlns="http://www.w3.org/2000/svg"><title id="tl-title">{e(desc)}</title>']
    step = 1 if (y1 - y0) <= 8 else 2
    for yr in range(y0, y1 + 1, step):
        x = x_of(date(yr, 1, 1))
        out.append(f'<line x1="{_num(x)}" y1="{_num(top)}" x2="{_num(x)}" y2="{_num(top + row_h * 6)}" '
                   f'stroke="{RING}"/>')
        out.append(f'<text x="{_num(x)}" y="{_num(top + row_h * 6 + 14)}" text-anchor="middle" font-size="10" '
                   f'fill="{INK2}">{yr}</text>')
    tx = x_of(today)
    out.append(f'<line x1="{_num(tx)}" y1="{_num(top)}" x2="{_num(tx)}" y2="{_num(top + row_h * 6)}" '
               f'stroke="{TEAL}" stroke-dasharray="3 3"><title>Research date {today.isoformat()}</title></line>')
    for i, a in enumerate(UMBRELLAS):
        cy = top + row_h * i + row_h / 2
        out.append(f'<text x="{_num(left - 8)}" y="{_num(cy + 4)}" text-anchor="end" font-size="11" '
                   f'fill="#1d2a31">{e(AREA_LABELS[a])}</text>')
        out.append(f'<line x1="{_num(left)}" y1="{_num(cy)}" x2="{_num(right)}" y2="{_num(cy)}" '
                   f'stroke="#eef1f3"/>')
    placed: dict[UmbrellaId, list[float]] = {a: [] for a in UMBRELLAS}
    offsets = (0.0, -6.0, 6.0, -3.0, 3.0)
    for ev in events:
        a = ev.flag.area
        x = x_of(ev.when)
        k = sum(1 for px in placed[a] if abs(px - x) < 10)
        placed[a].append(x)
        cy = top + row_h * UMBRELLAS.index(a) + row_h / 2 + offsets[k % len(offsets)]
        tip = e(f"{COLOUR_WORD[ev.flag.colour]}, {ev.flag.event_date}: {ev.flag.summary}")
        out.append(_shape(ev.flag.colour, x, cy, tip))
    out.append("</svg>")
    return "".join(out)


# ---------------------------------------------------------------------------
# HTML pieces
# ---------------------------------------------------------------------------

CSS = """
:root{--ink:#1d2a31;--ink2:#56656f;--muted:#87949c;--line:#dce2e6;--bg:#f4f6f7;--card:#ffffff;
--teal:#0f6e74;--red:#d03b3b;--amber:#fab219;--green:#0ca30c;--serious:#ec835a;color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:12px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",
Roboto,Helvetica,Arial,sans-serif}
.page{position:relative;background:var(--card);width:210mm;max-width:calc(100% - 16px);min-height:297mm;margin:16px auto;
padding:13mm 14mm;box-shadow:0 1px 3px #0002}
h1{font-size:21px;margin:0 0 4px}
h2{font-size:13.5px;margin:14px 0 6px;padding-bottom:3px;border-bottom:2px solid var(--teal);color:var(--ink)}
h2 .no{display:inline-block;min-width:20px;color:var(--teal)}
h3{font-size:12px;margin:10px 0 4px;color:var(--ink)}
p{margin:4px 0}ul,ol{margin:4px 0;padding-left:18px}li{margin:2px 0}
a{color:var(--teal)}a.cite{text-decoration:none;font-size:11px;white-space:nowrap}
.kicker{font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--ink2)}
.small{font-size:11px}.muted{color:var(--muted)}.na{color:var(--muted);font-style:italic}
.fields{display:grid;grid-template-columns:repeat(5,auto);gap:2px 16px;margin:6px 0 2px;padding:6px 0;
border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.fields div{min-width:0}.fields .k{font-size:10px;color:var(--ink2);text-transform:uppercase;letter-spacing:.04em}
.fields .v{font-size:12px;font-weight:600;word-break:break-word}
.notice{border:1px solid var(--line);background:#fff8e6;padding:6px 9px;margin:8px 0;font-weight:600;font-size:12px}
.banner{border-left:6px solid var(--muted);background:#f1f3f4;padding:8px 12px;margin:6px 0 8px}
.banner .v{font-size:16px;font-weight:700;margin-bottom:2px}
.banner.red,.banner.critical{border-color:var(--red);background:#fbecec}
.banner.amber{border-color:var(--amber);background:#fff7e3}.banner.green{border-color:var(--green);background:#eaf6ea}
.glance{display:grid;grid-template-columns:200px 1fr;gap:14px;align-items:start;margin-top:6px}
.total{border:1px solid var(--line);padding:10px 12px}
.total .n{font-size:38px;font-weight:700;line-height:1}.total .n small{font-size:14px;color:var(--ink2);font-weight:400}
.total .lvl{display:inline-block;margin-top:6px;font-weight:600}
.bar{height:7px;background:#eef1f3;margin:4px 0 2px;position:relative}.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--teal)}
.sbar{display:inline-block;width:70px;height:7px;background:#eef1f3;position:relative;vertical-align:middle;margin-right:6px}
.sbar i{position:absolute;left:0;top:0;bottom:0}
.radarbox svg.radar{max-height:250px;margin:0 auto}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
svg{max-width:100%;height:auto;display:block}
table{border-collapse:collapse;width:100%;font-size:11.5px}th,td{text-align:left;vertical-align:top;padding:3px 5px;
border-bottom:1px solid var(--line)}th{color:var(--ink2);font-weight:600;background:#f7f9fa}
td.num,th.num{text-align:right;white-space:nowrap}
table.kv th{width:32%;background:none}
.st{white-space:nowrap}.g{font-size:12px}
.g.red{color:var(--red)}.g.amber{color:#c98a00}.g.green{color:var(--green)}.g.neutral{color:var(--muted)}.g.serious{color:var(--serious)}
.flags{padding-left:0}.flags li{list-style:none;padding-left:18px;text-indent:-18px}
.flags .g{display:inline-block;width:18px;text-indent:0}
.area{border:1px solid var(--line);margin:6px 0;break-inside:avoid}
.area .ah{display:flex;justify-content:space-between;gap:8px;background:#f7f9fa;padding:4px 8px;font-weight:600}
.area .ah .sc{font-weight:400;color:var(--ink2)}
.area ul{margin:4px 8px 6px}
.lbl{font-weight:600}
.tag{font-size:10.5px;color:var(--ink2);border:1px solid var(--line);padding:0 4px;margin-left:3px;white-space:nowrap}
.rid{font-size:10.5px;font-weight:700;color:var(--teal);text-decoration:none;margin-right:3px}
.legend{font-size:11px;color:var(--ink2);margin:2px 0 4px}.legend span{margin-right:12px}
table.heat{table-layout:fixed;font-size:11px}table.register,table.bd{table-layout:fixed}
table.heat th,table.heat td{border:1px solid #fff;text-align:center;vertical-align:middle;padding:5px}
table.heat th{background:#f1f3f4}table.heat td{height:46px}
table.heat td .pl{display:block;font-size:9.5px;color:var(--ink2);margin-bottom:2px}
table.heat td a{font-weight:700;color:var(--ink);text-decoration:none;margin:0 2px}
.p1{background:#f6cfcf}.p2{background:#fbdfcc}.p3{background:#fff0c4}.p4{background:#eef1f3}
.measures{margin:0;padding-left:14px}
.sources li{margin:2px 0;font-size:11px;word-break:break-word}
.sources .q{display:block;color:var(--ink2);font-style:italic;margin-left:6px}
table.bd{font-size:10.5px}table.bd td.rule{color:var(--ink2)}
table.bd tr.sub td{background:#f7f9fa;font-weight:600}
.cw{position:relative;display:inline}
.pop{display:none;position:absolute;z-index:20;right:-8px;top:1.5em;width:330px;max-width:80vw;background:#fff;
border:1px solid var(--line);box-shadow:0 4px 14px #0003;padding:8px 10px;font-size:11.5px;line-height:1.4;
text-indent:0;white-space:normal;color:var(--ink);font-weight:400;text-align:left;font-style:normal}
.cw:hover .pop,.cw:focus-within .pop{display:block}
.pop span{display:block}.pop-h{color:var(--ink2);margin-bottom:2px}.pop-t{font-weight:600;margin-bottom:4px}
.pop-q{background:#f7f9fa;border-left:3px solid var(--teal);padding:4px 6px;margin:4px 0}
.pop-n{color:var(--muted);font-style:italic}
mark{background:#fff0b3;color:inherit;padding:0 1px}
.badge{display:inline!important;font-size:10.5px;border:1px solid var(--line);padding:0 4px;margin-left:4px;white-space:nowrap}
.badge.unverified{background:#fff7e3}
.sr{position:absolute;left:0;top:0;width:1px;height:1px;margin:-1px;padding:0;border:0;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}
.runhead{font-size:10.5px;color:var(--muted);margin-bottom:4px}
footer.foot{margin-top:14px;padding-top:6px;border-top:1px solid var(--line);font-size:10.5px;color:var(--ink2)}
@page{size:A4;margin:11mm}
@media print{body{background:#fff}.page{margin:0;box-shadow:none;width:auto;min-height:0;padding:0;
break-after:page;page-break-after:always}.page:last-child{break-after:auto;page-break-after:auto}
a{color:var(--ink)}.pop{display:none!important}h2,h3{break-after:avoid}tr,li,.area{break-inside:avoid}
body{font-size:10.5px;line-height:1.35}h1{font-size:18px}h2{font-size:12px;margin:10px 0 4px}table{font-size:9.5px}
th,td{padding:2px 4px}.small,.sources li{font-size:9.5px}.sources{columns:2;column-gap:12px;font-size:9px}
.sources li{font-size:8.5px;margin:1px 0}svg.timeline{max-height:118px;width:auto;margin:0 auto}
.radarbox svg.radar{max-height:215px}.total .n{font-size:30px}.banner{padding:6px 10px}.banner .v{font-size:14px}
table.heat td{height:34px}table.bd{font-size:8.5px}}
@media (max-width:700px){.page{padding:16px;min-height:0}.glance,.two{grid-template-columns:1fr}
.fields{grid-template-columns:1fr 1fr}}
"""

PRIORITY_CLASS = {1: "p1", 2: "p2", 3: "p3", 4: "p4"}
STATUS_GLYPH_COLOUR = {"red": "red", "amber": "amber", "green": "green", "context": "neutral", "not_assessed": "neutral"}
ROW_GLYPH = {"finding": None, "checked": "green", "context": "neutral", "not_assessed": "neutral", "pointer": "neutral"}


def _glyph(colour: str) -> str:
    return f'<span class="g {colour}" aria-hidden="true">{COLOUR_GLYPH.get(colour, "○")}</span>'


def _level_chip(level: str | None) -> str:
    if not level:
        return '<span class="muted">—</span>'
    cls = LEVEL_COLOUR.get(level, "neutral")
    return f'<span class="st"><span class="g {cls}" aria-hidden="true">■</span> {e(level)}</span>'


class _Chips:
    """[n] citation links with a pure-CSS popover showing the quote in its page context."""

    def __init__(self) -> None:
        self._pop = 0

    def chip(self, c: Mapping[str, Any]) -> str:
        self._pop += 1
        pid = f"cp-{self._pop}"
        unverified = c.get("trust") == "unverified"
        mark = UNVERIFIED_MARK if unverified else ""
        link_raw = str(c.get("link") or "")
        href = safe_url(link_raw.split("#", 1)[0])
        link = e(link_raw) if href else ""
        badge = f'<span class="badge {e(c.get("trust") or "")}">{e(c.get("trust_label") or "")}</span>'
        quote_ = str(c.get("quote") or "")
        if quote_:
            ex = str(c.get("excerpt") or "")
            qs, qe = int(c.get("quote_start") or 0), int(c.get("quote_end") or 0)
            q = f'{_ex(ex[:qs])}<mark>{_ex(ex[qs:qe])}</mark>{_ex(ex[qe:])}'
            ctx = "" if c.get("context_found") else '<span class="pop-n">Quote as stored; page context not saved.</span>'
            body = f'<span class="pop-q">{q}</span>{ctx}'
        else:
            body = '<span class="pop-n">Supporting source for this point; no quote stored from it.</span>'
        open_link = (f'<a class="pop-a" href="{link}" rel="noopener noreferrer">'
                     f'{"Open source at this passage" if quote_ else "Open source"}</a>' if href else "")
        pop = (f'<span class="pop" role="tooltip" id="{pid}"><span class="pop-h">{e(c.get("publisher") or "")} · '
               f'{e(c.get("published") or "date not stated")} {badge}</span><span class="pop-t">{e(c.get("title") or "")}'
               f'</span>{body}{open_link}</span>')
        label = f"[{int(c.get('id') or 0)}]{mark}"
        anchor = (f'<a class="cite" href="{link}" aria-describedby="{pid}" rel="noopener noreferrer">{label}</a>'
                  if href else f'<span class="cite" tabindex="0" aria-describedby="{pid}">{label}</span>')
        return f'<span class="cw">{anchor}{pop}</span>'

    def many(self, cites: list[Mapping[str, Any]]) -> str:
        return " ".join(self.chip(c) for c in cites)


def _h2(s: Mapping[str, Any]) -> str:
    return f'<h2 id="sec-{e(s["id"])}"><span class="no">{s["number"]}</span> {e(s["title"])}</h2>'


def _tags_html(tags: list[str]) -> str:
    return "".join(f'<span class="tag">{e(t)}</span>' for t in tags)


def _when(date_: str | None) -> str:
    return f' <span class="muted">({e(date_)})</span>' if date_ else ' <span class="muted">(date not stated)</span>'


def _score_cell(a: Mapping[str, Any]) -> str:
    if a.get("score") is not None:
        return f'{a["score"]} · {_level_chip(a.get("level"))}'
    return f'<span class="na">{e(a.get("no_score") or "Not assessed")}</span>'


def _evidence_cell(a: Mapping[str, Any]) -> str:
    used = []
    if a.get("trusted_pages"):
        used.append(plural(int(a["trusted_pages"]), "trusted page"))
    if a.get("unverified_pages"):
        used.append(f'{UNVERIFIED_MARK} {plural(int(a["unverified_pages"]), "unverified page")}')
    return " + ".join(used) or '<span class="muted">none</span>'


def _header_html(s: Mapping[str, Any]) -> str:
    fields = "".join(f'<div><div class="k">{e(f["label"])}</div><div class="v{" na" if f["value"] == "Not found" else ""}">'
                     f'{e(f["value"])}</div></div>' for f in s["fields"])
    searched = f'<div class="small muted">Searched as “{e(s["searched_as"])}”</div>' if s.get("searched_as") else ""
    notices = "".join(f'<div class="notice" role="note">{e(n)}</div>' for n in s.get("notices") or [])
    return (f'<header id="sec-header"><div class="kicker">{e(s["title"])} · structured after BAFA’s risk-analysis guide</div>'
            f'<h1>{e(s["company"])}</h1>{searched}<div class="fields">{fields}</div></header>{notices}')


def _total_html(t: Mapping[str, Any]) -> str:
    cov = t.get("coverage_pct")
    cov_word = "Coverage" if t.get("scored") else "Evidence coverage"
    cov_html = (f'<div class="small" style="margin-top:8px">{cov_word} {cov}%</div>'
                f'<div class="bar" role="img" aria-label="{cov_word} {cov} percent"><i style="width:{cov}%"></i></div>'
                f'<div class="small muted">share of the score weight backed by evidence</div>'
                if cov is not None else "")
    rng = t.get("range")
    rng_html = (f'<div class="small muted">If the missing scores were 0 or 100: {rng[0]}–{rng[1]}</div>'
                if rng and t.get("scored") else "")
    if t.get("score") is not None:
        main = (f'<div class="n">{t["score"]}<small> /100</small></div>'
                f'<div class="lvl">{_level_chip(t.get("level"))}</div>')
    else:
        main = f'<div class="n">—<small> /100</small></div><div class="lvl na">{e(t.get("no_total") or "")}</div>'
    return (f'<div class="total"><div class="small muted">Total risk score</div>{main}{cov_html}{rng_html}'
            f'<div class="small muted" style="margin-top:6px">0–100, higher means more risk. {e(t["bands"])}.</div></div>')


def _area_strip(areas: list[Mapping[str, Any]]) -> str:
    rows = []
    for a in areas:
        if a.get("score") is not None:
            colour = LEVEL_HEX.get(str(a.get("level")), TEAL)
            bar = f'<span class="sbar" aria-hidden="true"><i style="width:{a["score"]}%;background:{colour}"></i></span>'
            cell = f'<td class="num">{a["score"]}</td><td>{bar}{_level_chip(a.get("level"))}</td>'
        else:
            cell = f'<td class="num muted">—</td><td class="na">{e(a.get("no_score") or "Not assessed")}</td>'
        rows.append(f'<tr><td>{e(a["label"])}</td>{cell}</tr>')
    return ('<table class="strip" aria-label="Risk score by area"><thead><tr><th>Risk area</th><th class="num">Score</th>'
            f'<th>Level</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')


def _finding_li(item: Mapping[str, Any], chips: _Chips, with_area: bool = False, anchor: bool = False) -> str:
    colour = str(item.get("colour") or "neutral")
    kind = item.get("kind", "finding")
    glyph_colour = ROW_GLYPH.get(str(kind)) or colour
    rid = (f'<a class="rid" href="#risk-{e(item["risk_id"])}">{e(item["risk_id"])}</a>'
           if item.get("risk_id") else "")
    label = f'<span class="lbl">{e(item.get("label") or "")}:</span> '
    area = f' <span class="muted small">· {e(item["area_label"])}</span>' if with_area and item.get("area_label") else ""
    when = _when(item.get("date")) if item.get("flag_id") else ""
    idattr = f' id="flag-{e(item["flag_id"])}"' if anchor and item.get("flag_id") else ""
    return (f'<li{idattr}>{_glyph(glyph_colour)}{rid}{label}{e(item.get("summary") or "")}{when}{area}'
            f'{_tags_html(list(item.get("tags") or []))} {chips.many(list(item.get("cites") or []))}</li>')


def _summary_html(s: Mapping[str, Any], chips: _Chips) -> str:
    tone = s["tone"]
    tone_word = {"critical": "Knock-out risk", "red": "Red flags", "amber": "Watch items",
                 "green": "No red flags found", "neutral": "Not enough evidence"}[tone]
    if s.get("message"):
        return f'{_h2(s)}<div class="banner {tone}" role="status"><div class="v">{e(s["message"])}</div></div>'
    text = f"<p>{e(s['text'])}</p>" if s.get("text") else ""
    banner = (f'<div class="banner {tone}" role="status"><span class="sr">{e(tone_word)}. </span>'
              f'<div class="v">{e(s.get("verdict") or tone_word)}</div>{text}</div>')
    items = "".join(_finding_li(i, chips, with_area=True) for i in s["key_findings"])
    no = f'<p>{e(s["no_findings"])}</p>' if s.get("no_findings") else ""
    findings = (f'<h3>Most important findings</h3>{no}<ul class="flags">{items}</ul>' if items or no else "")
    na = (f'<p class="small"><strong>Not assessed:</strong> {e(", ".join(s["not_assessed"]))}. No verified facts were '
          'found for these areas, so nothing is known about them yet.</p>' if s.get("not_assessed") else "")
    ov = "".join(f'<p class="small"><strong>Override:</strong> {e(o)}</p>' for o in s.get("overrides") or [])
    return (f'{_h2(s)}{banner}<div class="glance">{_total_html(s["total"])}<div>{_area_strip(s["areas"])}</div></div>'
            f'{ov}{findings}{na}')


def _profile_html(s: Mapping[str, Any], chips: _Chips) -> str:
    rows = []
    for f in s["fields"]:
        val = (f'<span class="na">{e(f["value"])}</span>' if f["state"] != "found" else
               f'{e(f["value"])} {chips.many(list(f.get("cites") or []))}')
        rows.append(f'<tr><th scope="row">{e(f["label"])}</th><td>{val}</td></tr>')
    return f'{_h2(s)}<table class="kv"><tbody>{"".join(rows)}</tbody></table>'


def _country_html(s: Mapping[str, Any], chips: _Chips) -> str:
    a = s["area_score"]
    head = (f'<p>Country: <strong>{e(s["country"])}</strong> · Country &amp; Location score: {_score_cell(a)}</p>')
    if s["indicators"]:
        rows = "".join(f'<tr><td>{e(i["label"])}</td><td class="num">{e(i["value"])}</td><td>{e(i.get("year") or "")}'
                       f'</td><td>{e(i["band"]) or "—"}</td><td class="small muted">{e(i["scale"])}</td>'
                       f'<td>{chips.many(list(i.get("cites") or []))}</td></tr>' for i in s["indicators"])
        table = ('<table><thead><tr><th>Indicator</th><th class="num">Value</th><th>Year</th><th>Reading</th>'
                 f'<th>Scale</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>')
    else:
        table = '<p class="na">No country index data found.</p>'
    sec = s["sector"]
    sector = (f'<table class="kv" style="margin-top:6px"><tbody><tr><th scope="row">{e(sec["label"])}</th>'
              f'<td><span class="na">{e(sec["value"])}</span> <span class="small muted">{e(sec["note"])}</span></td>'
              '</tr></tbody></table>')
    return f'{_h2(s)}{head}{table}{sector}'


def _company_html(s: Mapping[str, Any], chips: _Chips, r: ResearchResult) -> str:
    blocks = []
    for a in s["areas"]:
        glyph = _glyph(STATUS_GLYPH_COLOUR[a["status"]])
        rows = "".join(_finding_li(i, chips, anchor=True) for i in a["rows"])
        blocks.append(f'<div class="area"><div class="ah"><span>{glyph} {e(a["label"])} · {e(a["status_label"])}</span>'
                      f'<span class="sc">Score: {_score_cell(a["score"])}</span></div><ul class="flags">{rows}</ul></div>')
    tl = s["timeline"]
    legend = ('<div class="legend"><span>' + _glyph("red") + ' Red flag</span><span>' + _glyph("amber") +
              ' Watch item</span><span>' + _glyph("green") + ' Strength</span><span style="color:' + TEAL +
              '">┆ research date</span><span>context facts not plotted</span></div>')
    rows_t = "".join(f'<tr><td>{e(ev["date"] or "")}</td><td>{e(ev["area_label"])}</td><td>{e(ev["label"])}</td>'
                     f'<td>{e(ev["summary"])}</td></tr>' for ev in tl["events"])
    table = (f'<div class="sr"><table><caption>Dated findings</caption><thead><tr><th>Date</th><th>Area</th>'
             f'<th>Type</th><th>Finding</th></tr></thead><tbody>{rows_t}</tbody></table></div>')
    notes = []
    if not tl["events"]:
        notes.append("No dated findings in the sources checked.")
    if tl["undated"]:
        notes.append(f"{plural(int(tl['undated']), 'finding')} without a date not shown.")
    note_html = f'<p class="small muted">{" ".join(e(n) for n in notes)}</p>' if notes else ""
    return (f'{_h2(s)}<p class="small muted">Findings per risk area, most serious first, each with its date and '
            f'source.</p>{"".join(blocks)}'
            f'<h3>Event timeline</h3>{legend}{timeline_svg(r)}{table}{note_html}')


def _heatmap_html(hm: Mapping[str, Any]) -> str:
    head = "".join(f'<th scope="col">{e(c["label"])}</th>' for c in hm["columns"])
    body = []
    for row in hm["rows"]:
        cells = []
        for c in row["cells"]:
            links = " ".join(f'<a href="#risk-{e(x["risk_id"])}" title="{e(x["summary"])}">{e(x["risk_id"])}</a>'
                             for x in c["risks"]) or '<span class="muted">—</span>'
            label = f'{row["label"]} severity, {c["label"]} likelihood: {c["priority_label"]}'
            cells.append(f'<td class="{PRIORITY_CLASS.get(int(c["priority"]), "p4")}" aria-label="{e(label)}">'
                         f'<span class="pl">{e(c["priority_label"])}</span>{links}</td>')
        body.append(f'<tr><th scope="row">{e(row["label"])}</th>{"".join(cells)}</tr>')
    return ('<table class="heat" aria-label="Risks by likelihood and severity"><thead><tr>'
            f'<th>Severity ↓ / Likelihood →</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>')


def _weighting_html(s: Mapping[str, Any], r: ResearchResult) -> str:
    rows = "".join(f'<tr><td>{e(a["label"])}</td><td class="st">{_score_cell(a)}</td>'
                   f'<td class="num">{a["weight_pct"] if a.get("weight_pct") is not None else "—"}'
                   f'{"%" if a.get("weight_pct") is not None else ""}</td><td>{_evidence_cell(a)}</td></tr>'
                   for a in s["areas"])
    t = s["total"]
    total_row = (f'<tr><td><strong>Total</strong></td><td class="st"><strong>{t["score"]}</strong> · '
                 f'{_level_chip(t.get("level"))}</td><td class="num">100%</td><td>coverage {t["coverage_pct"]}%</td></tr>'
                 if t.get("score") is not None else
                 f'<tr><td><strong>Total</strong></td><td class="na" colspan="3">{e(t.get("no_total") or "")}</td></tr>')
    table = ('<table aria-label="Area scores"><thead><tr><th>Risk area</th><th>Score · level</th><th class="num">Weight</th>'
             f'<th>Evidence used</th></tr></thead><tbody>{rows}{total_row}</tbody></table>'
             f'<p class="small muted">0–100, higher means more risk. {e(t["bands"])}.</p>')
    radar = (f'<div class="radarbox"><div class="small muted">Risk profile by area · hollow marker = not assessed'
             f'</div>{radar_svg(r)}</div>')
    hm = s["heatmap"]
    hm_note = ("Each red flag and watch item from section 4, placed by severity and likelihood. The codes link to the "
               "risk register." if hm["placed"] else "No red flags or watch items to place.")
    buyer = "".join(f'<tr><th scope="row">{e(b["label"])}</th><td class="na">{e(b["value"])}</td></tr>'
                    for b in s["buyer_inputs"])
    return (f'{_h2(s)}<div class="two">{radar}<div>{table}</div></div>'
            f'<h3>Likelihood and severity</h3><p class="small muted">{e(hm_note)}</p>{_heatmap_html(hm)}'
            f'<h3>Factors only the buyer can assess</h3><table class="kv"><tbody>{buyer}</tbody></table>')


def _register_html(s: Mapping[str, Any], chips: _Chips) -> str:
    if not s["rows"]:
        return f'{_h2(s)}<p>{e(s["empty"])}</p>'
    rows = []
    for x in s["rows"]:
        area_sc = (f'{x["area_score"]} · {e(x["area_level"] or "")}' if x.get("area_score") is not None
                   else f'<span class="na">{e(x.get("area_no_score") or "Not assessed")}</span>')
        measures = "".join(f"<li>{e(m)}</li>" for m in x["measures"])
        rows.append(
            f'<tr id="risk-{e(x["risk_id"])}"><td><a class="rid" href="#flag-{e(x["flag_id"])}">{e(x["risk_id"])}</a></td>'
            f'<td>{_glyph(x["colour"])} {e(x["description"])}{_when(x.get("date"))}{_tags_html(list(x["tags"]))} '
            f'{chips.many(list(x["cites"]))}</td><td>{e(x["area_label"])}</td><td class="na">{e(x["owner"])}</td>'
            f'<td><span class="st">{e(x["priority_label"])}</span><br><span class="small muted">Severity '
            f'{e(x["severity"])} · likelihood {e(x["likelihood"])}<br>Area score {area_sc}</span></td>'
            f'<td><ul class="measures small">{measures}</ul></td></tr>')
    cols = "".join(f'<col style="width:{w}%">' for w in (5, 36, 12, 9, 16, 22))
    return (f'{_h2(s)}<table class="register"><colgroup>{cols}</colgroup><thead><tr><th>ID</th><th>Risk</th><th>Area</th><th>Owner</th>'
            f'<th>Weighting</th><th>Suggested measures</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')


def _prevention_html(s: Mapping[str, Any]) -> str:
    items = []
    for st in s["steps"]:
        tied = ", ".join(f'<a class="rid" href="#risk-{e(x["risk_id"])}">{e(x["risk_id"])}</a>' for x in st["risks"])
        tail = f' <span class="small muted">Addresses {tied}</span>' if tied else ""
        items.append(f"<li>{e(st['text'])}{tail}</li>")
    return (f'{_h2(s)}<p class="small muted">Next steps for the buyer, starting with the highest-priority risks.</p>'
            f'<ol>{"".join(items)}</ol>')


def _bd_line(x: Mapping[str, Any], chips: _Chips) -> str:
    kind = {"base": "Starting value", "event": "Fact counted", "not_counted": "Fact not counted",
            "override": "Override", "cap": "Cap", "input_not_used": "Input not used"}.get(str(x["kind"]), str(x["kind"]))
    pts = "" if x.get("points") is None else f'{x["points"]:.1f}'
    rid = f'<a class="rid" href="#risk-{e(x["risk_id"])}">{e(x["risk_id"])}</a>' if x.get("risk_id") else ""
    return (f'<tr><td class="st">{e(kind)}</td><td>{rid}{e(x["label"])} {chips.many(list(x.get("cites") or []))}</td>'
            f'<td class="num">{pts}</td><td class="rule">{e(x["rule"])}</td></tr>')


def _documentation_html(s: Mapping[str, Any], chips: _Chips) -> str:
    method = "".join(f"<li>{e(m)}</li>" for m in s["method"])
    w = ", ".join(f'{x["label"]} {x["pct"]}%' for x in s["weights"])
    weights = f'<p class="small">Area weights: {e(w)}.</p>' if w else ""
    tm = f'<p class="small">Total in this report: {e(s["total_method"])}.</p>' if s.get("total_method") else ""
    hr = s["heatmap_rule"]

    def rule_table(title: str, rows: list[list[str]]) -> str:
        body = "".join(f"<tr><td>{e(c)}</td><td>{e(v)}</td></tr>" for c, v in rows)
        return (f'<table class="small"><thead><tr><th>{e(title)}: when the fact is …</th><th>Result</th></tr></thead>'
                f'<tbody>{body}</tbody></table>')

    heat = (f'<h3>Heatmap rule</h3><p class="small">{e(hr["note"])} Rules are read top to bottom; the first that fits '
            f'applies.</p><div class="two">{rule_table("Severity", hr["severity"])}'
            f'{rule_table("Likelihood", hr["likelihood"])}</div>')
    bd = s["breakdown"]
    if bd["available"]:
        parts = []
        for a in bd["areas"]:
            score = (f'{a["score"]} · {e(a["level"] or "")}' if a.get("score") is not None else
                     f'<span class="na">{e(a.get("no_score") or "Not assessed")}</span>')
            rows = [f'<tr class="sub"><td colspan="4">{e(a["label"])} · {score}</td></tr>']
            for sub in a["sub_scores"]:
                sc = (f'{sub["score"]}' if sub.get("score") is not None else
                      f'<span class="na">{e(sub.get("not_assessed") or "Not assessed")}</span>')
                wt = f' · weight {sub["weight_pct"]}%' if sub.get("weight_pct") is not None else ""
                rows.append(f'<tr><td colspan="4"><strong>{e(sub["label"])}</strong>: {sc}{wt}</td></tr>')
                rows += [_bd_line(x, chips) for x in sub["lines"]]
            rows += [_bd_line(x, chips) for x in a["overrides"]]
            parts.append("".join(rows))
        rows_total = "".join(_bd_line(x, chips) for x in bd["total_overrides"])
        if rows_total:
            parts.append(f'<tr class="sub"><td colspan="4">Total</td></tr>{rows_total}')
        cols = "".join(f'<col style="width:{w}%">' for w in (12, 36, 7, 45))
        breakdown = (f'<table class="bd"><colgroup>{cols}</colgroup><thead><tr><th>Line</th><th>What</th><th class="num">Points</th>'
                     f'<th>Rule</th></tr></thead><tbody>{"".join(parts)}</tbody></table>')
    else:
        breakdown = ""
    bd_html = f'<h3>How each fact was scored</h3><p class="small muted">{e(bd["note"])}</p>{breakdown}'
    if s["followups"]:
        fus = "".join(
            f'<li><strong>{e(x["question"])}</strong>'
            + (f' <span class="muted">(on <a class="rid" href="#risk-{e(x["risk_id"])}">{e(x["risk_id"])}</a>)</span>'
               if x.get("risk_id") else "")
            + f' {e(x["outcome"])} {chips.many(list(x["cites"]))}</li>' for x in s["followups"])
        fu_html = f'<h3>Follow-up checks</h3><ul class="small">{fus}</ul>'
    else:
        fu_html = ('<h3>Follow-up checks</h3><p class="small">No follow-up searches were needed: no red flag or watch '
                   'item called for a deeper check.</p>')
    limits = "".join(f"<li>{e(x)}</li>" for x in s["limits"])
    items = []
    for src in s["sources"]:
        url = safe_url(src["url"])
        link = (f'<a href="{e(url)}" rel="noopener noreferrer">{e(url)}</a>' if url else
                f'<span class="muted">{e(src["url"])}</span>')
        quotes = "".join(f'<span class="q">“{e(q)}”</span>' for q in src["quotes"])
        items.append(f'<li id="src-{src["num"]}" value="{src["num"]}">{e(src["trust_label"])} · {e(src["title"])} — '
                     f'{e(src["publisher"])}. Published {e(src["published"] or "date not stated")}, accessed '
                     f'{e(src["accessed"])}. {link}{quotes}</li>')
    srcs = f'<ol class="sources">{"".join(items)}</ol>' if items else "<p>No sources cited.</p>"
    unc = s["uncited"]
    tail = (f'<p class="small muted">{plural(unc, "further source")} checked but not cited.</p>' if unc > 0 else "")
    return (f'{_h2(s)}<h3>How the scores work</h3><ul class="small">{method}</ul>{weights}{tm}{heat}{bd_html}{fu_html}'
            f'<h3>Limits of this report</h3><ul class="small">{limits}</ul>'
            f'<h3>Sources</h3><p class="small muted">{TRUSTED_MARK} on our trusted source list · {UNVERIFIED_MARK} '
            f'{UNVERIFIED_TEXT} (a fact found only there is at most a watch item) · company-stated = the company’s own '
            f'site.</p>{srcs}{tail}')


def _footer_html(s: Mapping[str, Any]) -> str:
    return (f'<footer class="foot" id="sec-footer">{e(s["text"])} Structure source: <a href="{e(s["link"])}" '
            f'rel="noopener noreferrer">{e(s["link_label"])}</a>. Laid out by fixed rules from the research data.</footer>')


def _doc(title: str, body: str) -> str:
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(title)}</title><style>{CSS}</style></head><body>{body}</body></html>\n')


def _special_page(r: ResearchResult, sections: list[dict[str, Any]]) -> str | None:
    """Single page for needs_clarification and error results."""
    head = _header_html(sections[0])
    foot = _footer_html(sections[-1])
    if r.status == "needs_clarification" and r.clarification:
        rows = "".join(f"<tr><td>{e(c.legal_name)}</td><td>{e(c.country_name or c.country_code or '—')}</td>"
                       f"<td>{e(c.website or '—')}</td></tr>" for c in r.clarification.candidates)
        table = (f'<table><thead><tr><th>Company</th><th>Country</th><th>Website</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table>') if rows else ""
        return (f'<section class="page">{head}<div class="banner"><div class="v">We need one detail before '
                f'researching</div><p>{e(r.clarification.question)}</p></div>{table}{foot}</section>')
    if r.status == "error":
        msg = "; ".join(r.warnings) or "unknown error"
        return (f'<section class="page">{head}<div class="banner red"><div class="v">Research failed</div>'
                f'<p>{e(msg)}</p></div><p>No risk assessment was made. Try again or contact the team.</p>{foot}</section>')
    return None


def load_input(result: ResearchResult | Mapping[str, Any] | str | Path,
               page_texts: Mapping[str, str] | None = None) -> tuple[ResearchResult, Evidence]:
    """The validated result plus any page text / quote context found in the raw input."""
    raw: object = result
    if isinstance(result, (str, Path)):
        raw = json.loads(Path(result).read_text(encoding="utf-8"))
    r = as_result(raw if isinstance(raw, Mapping) else result)
    return r, _extract_evidence(raw, page_texts)


def report_sections(result: ResearchResult | Mapping[str, Any] | str | Path,
                    page_texts: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """The report's ordered sections as plain dicts (see report_data.py); same order as render_html."""
    from .report_data import report_sections as _sections

    return _sections(result, page_texts)


def render_html(result: ResearchResult | Mapping[str, Any] | str | Path,
                page_texts: Mapping[str, str] | None = None) -> str:
    """Render the buyer report as one self-contained HTML document (deterministic, no scripts).

    ``page_texts`` (source id -> page text) is optional; with it, each citation popover shows
    the quote inside its surrounding text."""
    from .report_data import build_sections

    r, evidence = load_input(result, page_texts)
    sections = build_sections(r, evidence)
    by = {s["id"]: s for s in sections}
    title = f"Supplier risk report: {company_name(r)}"
    special = _special_page(r, sections)
    if special is not None:
        return _doc(title, special)
    chips = _Chips()
    run = (f'<div class="runhead">{e(company_name(r))} · researched {e(r.researched_at[:10])}</div>')
    page1 = (f'<section class="page" aria-label="Summary and profile">{_header_html(by["header"])}'
             f'{_summary_html(by["summary"], chips)}{_profile_html(by["profile"], chips)}'
             f'{_country_html(by["country_sector"], chips)}</section>')
    page2 = (f'<section class="page" aria-label="Risks found and weighting">{run}'
             f'{_company_html(by["company_risks"], chips, r)}{_weighting_html(by["weighting"], r)}</section>')
    page3 = (f'<section class="page" aria-label="Register, prevention and documentation">{run}'
             f'{_register_html(by["register"], chips)}{_prevention_html(by["prevention"])}'
             f'{_documentation_html(by["documentation"], chips)}{_footer_html(by["footer"])}</section>')
    return _doc(title, page1 + page2 + page3)


def write_report_html(result: ResearchResult | Mapping[str, Any] | str | Path, path: str | Path,
                      page_texts: Mapping[str, str] | None = None) -> Path:
    """Write report.html; ``path`` may be a directory (then ``report.html`` inside it)."""
    p = Path(path)
    if p.is_dir():
        p = p / "report.html"
    p.write_text(render_html(result, page_texts), encoding="utf-8")
    return p


def page_texts_from_file(result: ResearchResult, path: Path) -> dict[str, str]:
    """Page texts for citation context from a JSON file: either {source_id: text} or a list of
    {"url", "raw_content"} documents (the offline fixture's format), matched to sources by URL."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, Mapping) and isinstance(data.get("documents"), list):
        data = data["documents"]
    if isinstance(data, Mapping):
        return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}
    by_url = {str(d.get("url")): str(d.get("raw_content") or "") for d in data if isinstance(d, Mapping)}
    return {s.id: by_url[s.url] for s in result.sources if by_url.get(s.url)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render report.html from a result.json.")
    ap.add_argument("result_json", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=None, help="output file or folder (default: next to input)")
    ap.add_argument("--page-texts", type=Path, default=None,
                    help="optional JSON with page texts for citation context ({source_id: text} or fixture documents)")
    args = ap.parse_args(argv)
    data = json.loads(args.result_json.read_text(encoding="utf-8"))
    texts = page_texts_from_file(as_result(data), args.page_texts) if args.page_texts else None
    out = write_report_html(data, args.out or args.result_json.parent, texts)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
