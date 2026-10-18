"""Deterministic two-page HTML risk report rendered from a ResearchResult (or its result.json).

No model writes layout or wording here: the same result always gives the same bytes. Charts
are inline SVG built by code (no JavaScript, no external assets), each with an aria-label and
a table fallback, and the page prints to A4 (two pages at most for normal results).

Page 1, at a glance: header, verdict banner, total score with level and coverage, a 6-axis
radar of the area scores (not-assessed axes drawn hollow, never as 0), top red flags and
watch items, strengths, next steps.
Page 2, detail: per-area table, event timeline, what we dug into, method note, limits,
sources with trust labels and dates.

Usage: ``python -m research_agent.report_html path/to/result.json [-o report.html]``.
The template research behind this layout is in docs/research/report-template.md.
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
from .models import UMBRELLAS, AreaScore, AreaStatus, Flag, ResearchResult, Source, UmbrellaId
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
AREA_STATUS_WORD = {"red": "Red flag", "amber": "Watch", "green": "No issues found",
                    "context": "Context only", "not_assessed": "Not assessed"}
AREA_STATUS_COLOUR = {"red": "red", "amber": "amber", "green": "green", "context": "neutral",
                      "not_assessed": "neutral"}
LEVEL_COLOUR = {"Low": "green", "Medium": "amber", "High": "serious", "Critical": "red"}
LEVEL_HEX = {"Low": "#0ca30c", "Medium": "#fab219", "High": "#ec835a", "Critical": "#d03b3b"}
TEAL = "#0f6e74"
RING = "#dce2e6"
MUTED = "#87949c"
INK2 = "#56656f"

TRUSTED_MARK = "✅"
UNVERIFIED_MARK = "🟨"
UNVERIFIED_TEXT = "not in our trusted source list"

CAP_P1_RED, CAP_P1_AMBER, CAP_P1_GREEN = 3, 3, 3
CAP_NEXT_STEPS = 3
CAP_SOURCES = 12

METHOD_NOTE = ("Scores come from our published fact-to-number method (docs/research/facts-to-scores.md); "
               "weights come from the challenge dataset. 0–100, higher means more risk. An area without "
               "evidence is “Not assessed”: no score, never 0; the total covers assessed areas only. "
               "A fact found only on a site not in our trusted list counts for less and is never a knock-out.")


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
.page{background:var(--card);width:210mm;max-width:calc(100% - 16px);min-height:297mm;margin:16px auto;padding:13mm 14mm;
box-shadow:0 1px 3px #0002}
h1{font-size:20px;margin:0 0 2px}h2{font-size:13px;margin:11px 0 5px;padding-bottom:3px;border-bottom:1px solid var(--line)}
p{margin:4px 0}ul{margin:4px 0;padding-left:18px}li{margin:2px 0}
a{color:var(--teal)}a.cite{text-decoration:none;font-size:11px;white-space:nowrap}
.meta{color:var(--ink2);font-size:12px}.small{font-size:11px}.muted{color:var(--muted)}
.notice{border:1px solid var(--line);background:#fff8e6;padding:6px 9px;margin:8px 0;font-weight:600;font-size:12px}
.banner{border-left:6px solid var(--muted);background:#f1f3f4;padding:9px 12px;margin:10px 0 8px}
.banner .v{font-size:17px;font-weight:700}
.banner.red,.banner.critical{border-color:var(--red);background:#fbecec}
.banner.critical .v{text-transform:none}
.banner.amber{border-color:var(--amber);background:#fff7e3}.banner.green{border-color:var(--green);background:#eaf6ea}
.glance{display:grid;grid-template-columns:190px 1fr;gap:14px;align-items:start;margin-top:6px}
.total{border:1px solid var(--line);padding:10px 12px}
.total .n{font-size:40px;font-weight:700;line-height:1}.total .n small{font-size:14px;color:var(--ink2);font-weight:400}
.total .lvl{display:inline-block;margin-top:6px;font-weight:600}
.bar{height:7px;background:#eef1f3;margin:4px 0 2px;position:relative}.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--teal)}
.radarbox svg.radar{max-height:250px;margin:0 auto}
svg{max-width:100%;height:auto;display:block}
table{border-collapse:collapse;width:100%;font-size:11.5px}th,td{text-align:left;vertical-align:top;padding:3px 5px;
border-bottom:1px solid var(--line)}th{color:var(--ink2);font-weight:600}
td.num{text-align:right;white-space:nowrap}
.st{white-space:nowrap}.g{font-size:12px}
.g.red{color:var(--red)}.g.amber{color:#c98a00}.g.green{color:var(--green)}.g.neutral{color:var(--muted)}.g.serious{color:var(--serious)}
.flags li{list-style:none;margin-left:-18px;padding-left:18px;text-indent:-18px}
.flags .g{display:inline-block;width:18px;text-indent:0}
.tag{font-size:10.5px;color:var(--ink2);border:1px solid var(--line);padding:0 4px;margin-left:3px;white-space:nowrap}
.legend{font-size:11px;color:var(--ink2);margin:2px 0 4px}.legend span{margin-right:12px}
.sources li{margin:2px 0;font-size:11px;word-break:break-word}
.cw{position:relative;display:inline}
.pop{display:none;position:absolute;z-index:20;right:-8px;top:1.5em;width:330px;max-width:80vw;background:#fff;
border:1px solid var(--line);box-shadow:0 4px 14px #0003;padding:8px 10px;font-size:11.5px;line-height:1.4;
text-indent:0;white-space:normal;color:var(--ink);font-weight:400;text-align:left}
.cw:hover .pop,.cw:focus-within .pop{display:block}
.pop span{display:block}.pop-h{color:var(--ink2);margin-bottom:2px}.pop-t{font-weight:600;margin-bottom:4px}
.pop-q{background:#f7f9fa;border-left:3px solid var(--teal);padding:4px 6px;margin:4px 0}
.pop-n{color:var(--muted);font-style:italic}
mark{background:#fff0b3;color:inherit;padding:0 1px}
.badge{display:inline!important;font-size:10.5px;border:1px solid var(--line);padding:0 4px;margin-left:4px;white-space:nowrap}
.badge.unverified{background:#fff7e3}
.sources .q{display:block;color:var(--ink2);font-style:italic;margin-left:6px}
.sr{position:absolute;left:0;top:0;width:1px;height:1px;margin:-1px;padding:0;border:0;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}
.page{position:relative}
.foot{margin-top:10px;font-size:10.5px;color:var(--muted)}
@page{size:A4;margin:10mm}
@media print{body{background:#fff}.page{margin:0;box-shadow:none;width:auto;min-height:0;padding:0;
break-after:page;page-break-after:always}.page:last-child{break-after:auto;page-break-after:auto}
a{color:var(--ink)}.pop{display:none!important}h2{break-after:avoid}tr,li{break-inside:avoid}
body{font-size:10.5px;line-height:1.35}h1{font-size:18px}h2{font-size:11.5px;margin:8px 0 3px}table{font-size:9.5px}th,td{padding:2px 4px}.small,.sources li{font-size:9.5px}.sources{columns:2;column-gap:12px;padding-left:16px;font-size:9px}.sources li{font-size:8.5px;margin:1px 0}svg.timeline{max-height:118px;width:auto;margin:0 auto}.radarbox svg.radar{max-height:215px}.total .n{font-size:32px}.banner{padding:6px 10px;margin:6px 0}.banner .v{font-size:14px}.foot{margin-top:4px}}
@media (max-width:700px){.page{padding:16px;min-height:0}.glance{grid-template-columns:1fr}}
"""


def _glyph(colour: str) -> str:
    return f'<span class="g {colour}" aria-hidden="true">{COLOUR_GLYPH.get(colour, "○")}</span>'


def _level_chip(level: str | None) -> str:
    if not level:
        return '<span class="muted">—</span>'
    cls = LEVEL_COLOUR.get(level, "neutral")
    return f'<span class="st"><span class="g {cls}" aria-hidden="true">■</span> {e(level)}</span>'


def _flag_li(f: Flag, cit: _Cites) -> str:
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
        tags.append(f"{UNVERIFIED_MARK} unverified source only" + (", capped at watch item" if f.capped_unverified else ""))
    tag_html = "".join(f'<span class="tag">{e(t)}</span>' for t in tags)
    when = f' <span class="muted">({e(f.event_date)})</span>' if f.event_date else ' <span class="muted">(date not stated)</span>'
    area = f' <span class="muted small">· {e(AREA_LABELS[f.area])}</span>'
    return (f'<li>{_glyph(f.colour)}<span class="sr">{COLOUR_WORD[f.colour]}: </span>{e(f.summary)}{when}{area}'
            f'{tag_html} {cit.cite_flag(f)}</li>')


def _flag_block(title: str, colour: str, flags: list[Flag], cap: int, empty: str, cit: _Cites) -> str:
    items = "".join(_flag_li(f, cit) for f in flags[:cap]) or f'<li>{_glyph("neutral")}{e(empty)}</li>'
    more = len(flags) - cap
    more_html = (f'<p class="small muted">+{more} more on page 2 (timeline) and in the full data.</p>'
                 if more > 0 else "")
    return f'<h2>{_glyph(colour)} {e(title)}</h2><ul class="flags">{items}</ul>{more_html}'


def _header(r: ResearchResult) -> str:
    name = company_name(r)
    meta: list[str] = []
    if r.entity:
        if r.entity.legal_name.strip().lower() != r.company_input.strip().lower():
            meta.append(f"Searched as “{e(r.company_input)}”")
        meta.append(e(r.entity.country_name or r.entity.country_code or "country unknown"))
        if r.entity.website:
            meta.append(e(r.entity.website))
    else:
        meta.append(e(r.country_input or "country unknown"))
    meta.append(f"Researched {e(r.researched_at[:10])}")
    st = r.stats
    pages = plural(st.pages_read, "source") + " checked"
    if st.unverified_pages_read:
        pages += f" ({st.trusted_pages_read} trusted, {UNVERIFIED_MARK} {st.unverified_pages_read} not in our trusted list)"
    meta.append(pages)
    desc = f'<p class="small muted">{e(r.entity.description)}</p>' if r.entity and r.entity.description else ""
    out = (f'<header><div class="small muted">Supplier risk research report</div><h1>{e(name)}</h1>'
           f'<div class="meta">{" · ".join(meta)}</div>{desc}</header>')
    if r.notice:
        out += f'<div class="notice" role="note">{e(r.notice)}</div>'
    if r.status == "partial":
        out += ('<div class="notice" role="note">Partial result: the run stopped early (time or budget limit). '
                'Some areas may be incomplete.</div>')
    return out


def _total_block(r: ResearchResult) -> str:
    cov = coverage_pct(r)
    scored = is_scored(r)
    cov_word = "Coverage" if scored else "Evidence coverage"
    cov_html = (f'<div class="small" style="margin-top:8px">{cov_word} {cov}%</div>'
                f'<div class="bar" role="img" aria-label="{cov_word} {cov} percent"><i style="width:{cov}%"></i></div>'
                f'<div class="small muted">share of the score weight backed by evidence</div>'
                if cov is not None else "")
    rng = score_range(r)
    rng_html = (f'<div class="small muted">If the missing scores were 0 or 100: {rng[0]}–{rng[1]}</div>'
                if rng and scored else "")
    if r.scores.total is not None:
        main = (f'<div class="n">{r.scores.total}<small> /100</small></div>'
                f'<div class="lvl">{_level_chip(r.scores.total_level)}</div>')
    elif scored:
        main = ('<div class="n">—<small> /100</small></div><div class="lvl muted">Total not shown: too little '
                'of the score weight has evidence</div>')
    else:
        main = '<div class="n">—<small> /100</small></div><div class="lvl muted">Not scored yet</div>'
    return (f'<div class="total"><div class="small muted">Total risk score</div>{main}{cov_html}{rng_html}'
            f'<div class="small muted" style="margin-top:6px">0–100, higher means more risk. {LEVEL_BANDS}.</div></div>')


def _radar_table(r: ResearchResult) -> str:
    scores = area_scores(r)
    rows = []
    for a in UMBRELLAS:
        s = scores[a]
        v = area_score_value(s)
        if v is not None:
            cell = f'<td class="num">{v}</td><td>{_level_chip(s.level)}</td>'
        else:
            cell = f'<td class="num muted">—</td><td class="muted">{no_score_label(r, s)}</td>'
        rows.append(f"<tr><td>{e(AREA_LABELS[a])}</td>{cell}</tr>")
    return ('<table class="radar-table" aria-label="Area scores (table version of the chart)">'
            '<thead><tr><th>Area</th><th class="num">Score</th><th>Level</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def _area_table(r: ResearchResult, cit: _Cites) -> str:
    scores = area_scores(r)
    status = {a.area: a for a in r.areas}
    flags_by_id = {f.id: f for f in r.flags}
    rows = []
    for a in UMBRELLAS:
        s = scores[a]
        st: AreaStatus | None = status.get(a)
        v = area_score_value(s)
        stat_key = st.status if st else "not_assessed"
        stat = f'{_glyph(AREA_STATUS_COLOUR[stat_key])} {AREA_STATUS_WORD[stat_key]}'
        score = f"{v} · {_level_chip(s.level)}" if v is not None else (
            f'<span class="muted">{no_score_label(r, s)}</span>')
        used = []
        if s.trusted_pages:
            used.append(plural(s.trusted_pages, "trusted page"))
        if s.unverified_pages:
            used.append(f"{UNVERIFIED_MARK} {plural(s.unverified_pages, 'unverified page')}")
        pages = " + ".join(used) or '<span class="muted">none</span>'
        finding = e(st.finding) if st else "Not assessed: no sources returned evidence."
        if st and st.flag_ids and st.flag_ids[0] in flags_by_id:
            finding += " " + cit.cite_flag(flags_by_id[st.flag_ids[0]])
        rows.append(f'<tr><td>{e(AREA_LABELS[a])}</td><td class="st">{stat}</td><td class="st">{score}</td>'
                    f'<td>{pages}</td><td>{finding}</td></tr>')
    return ('<table class="areas"><thead><tr><th>Area</th><th>Status</th><th>Score · level</th>'
            f'<th>Pages used</th><th>Finding</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')


def _timeline_block(r: ResearchResult) -> str:
    events, undated = timeline_events(r)
    legend = ('<div class="legend"><span>' + _glyph("red") + ' Red flag</span><span>' + _glyph("amber") +
              ' Watch item</span><span>' + _glyph("green") + ' Strength</span><span style="color:' + TEAL +
              '">┆ research date</span><span>context facts not plotted</span></div>')
    rows = "".join(f'<tr><td>{e(ev.flag.event_date or "")}</td><td>{e(AREA_LABELS[ev.flag.area])}</td>'
                   f'<td>{COLOUR_WORD[ev.flag.colour]}</td><td>{e(ev.flag.summary)}</td></tr>' for ev in events)
    table = (f'<div class="sr"><table><caption>Dated findings</caption><thead><tr><th>Date</th><th>Area</th>'
             f'<th>Type</th><th>Finding</th></tr></thead><tbody>{rows}</tbody></table></div>')
    notes = []
    if not events:
        notes.append("No dated findings in the sources checked.")
    if undated:
        notes.append(f"{plural(undated, 'finding')} without a date not shown.")
    return (f'<h2>Event timeline</h2>{legend}{timeline_svg(r)}{table}'
            + (f'<p class="small muted">{" ".join(e(n) for n in notes)}</p>' if notes else ""))


def _dug_into(r: ResearchResult, cit: _Cites) -> str:
    flags_by_id = {f.id: f for f in r.flags}
    if not r.followups:
        return ('<h2>What we dug into</h2><p>No follow-up searches were needed: no red flag or watch item '
                'warranted a deeper check.</p>')
    items = []
    for fu in r.followups:
        flag = flags_by_id.get(fu.flag_id)
        on = f' <span class="muted">(on {COLOUR_WORD[flag.colour].lower()} {cit.cite_flag(flag)})</span>' if flag else ""
        refs = cit.cite(fu.corroborating_source_ids)
        outcome = e(fu.outcome or "No new information found.")
        items.append(f"<li><strong>{e(fu.question)}</strong>{on} {outcome} {refs}</li>")
    return f'<h2>What we dug into</h2><ul>{"".join(items)}</ul>'


def _method(r: ResearchResult) -> str:
    weights = r.scores.weights
    w = ", ".join(f"{AREA_LABELS[a]} {round(weights[a] * 100)}%" for a in UMBRELLAS if a in weights)
    method = r.scores.total_method or "not scored yet"
    return (f'<h2>How the scores work</h2><p class="small">{e(METHOD_NOTE)}</p>'
            + (f'<p class="small">Weights: {e(w)}. Method used in this report: {e(method)}.</p>' if w else
               f'<p class="small">Method used in this report: {e(method)}.</p>')
            + '<p class="small">Flag colours are set by fixed rules, not by the AI.</p>')


def _sources(r: ResearchResult, cit: _Cites) -> str:
    items = []
    for i, sid in enumerate(cit.order[:CAP_SOURCES], start=1):
        s = cit.by_id[sid]
        if s.trust == "unverified":
            mark = f"{UNVERIFIED_MARK} {UNVERIFIED_TEXT}"
        else:
            mark = f"{TRUSTED_MARK} trusted" + (", company-stated" if s.tier == "company_own" else "")
        pub = normalize_date(s.published_date) or "date not stated"
        url = safe_url(s.url)
        link = (f'<a href="{e(url)}" rel="noopener noreferrer">{e(url)}</a>' if url else
                f'<span class="muted">{e(s.url)}</span>')
        quotes = "".join(f'<span class="q">“{e(q)}”</span>' for q in cit.quotes_by_source.get(sid, []))
        items.append(f'<li id="src-{i}" value="{i}">{mark} · {e(s.title)} — {e(s.publisher)}. '
                     f'Published {e(pub)}, accessed {e(s.retrieved_at[:10])}. {link}{quotes}</li>')
    extra = []
    over = len(cit.order) - CAP_SOURCES
    if over > 0:
        extra.append(f"{plural(over, 'further cited source')} in the full data.")
    uncited = len(r.sources) - len(cit.order)
    if uncited > 0:
        extra.append(f"{plural(uncited, 'further source')} checked but not cited {'is' if uncited == 1 else 'are'} "
                     "in the full data.")
    body = f'<ol class="sources">{"".join(items)}</ol>' if items else "<p>No sources cited.</p>"
    tail = f'<p class="small muted">{" ".join(extra)}</p>' if extra else ""
    return (f'<h2>Sources</h2><p class="small muted">{TRUSTED_MARK} on our trusted source list · {UNVERIFIED_MARK} '
            f'{UNVERIFIED_TEXT} (a fact found only there is at most a watch item) · company-stated = the '
            f'company’s own site.</p>{body}{tail}')


def _doc(title: str, body: str) -> str:
    return ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{e(title)}</title><style>{CSS}</style></head><body>{body}</body></html>\n')


def _special_page(r: ResearchResult) -> str | None:
    """Single page for needs_clarification and error results."""
    if r.status == "needs_clarification" and r.clarification:
        rows = "".join(f"<tr><td>{e(c.legal_name)}</td><td>{e(c.country_name or c.country_code or '—')}</td>"
                       f"<td>{e(c.website or '—')}</td></tr>" for c in r.clarification.candidates)
        table = (f'<table><thead><tr><th>Company</th><th>Country</th><th>Website</th></tr></thead>'
                 f'<tbody>{rows}</tbody></table>') if rows else ""
        return (f'<section class="page">{_header(r)}<div class="banner"><div class="v">We need one detail before '
                f'researching</div><p>{e(r.clarification.question)}</p></div>{table}</section>')
    if r.status == "error":
        msg = "; ".join(r.warnings) or "unknown error"
        return (f'<section class="page">{_header(r)}<div class="banner red"><div class="v">Research failed</div>'
                f'<p>{e(msg)}</p></div><p>No risk assessment was made. Try again or contact the team.</p></section>')
    return None


def load_input(result: ResearchResult | Mapping[str, Any] | str | Path,
               page_texts: Mapping[str, str] | None = None) -> tuple[ResearchResult, Evidence]:
    """The validated result plus any page text / quote context found in the raw input."""
    raw: object = result
    if isinstance(result, (str, Path)):
        raw = json.loads(Path(result).read_text(encoding="utf-8"))
    r = as_result(raw if isinstance(raw, Mapping) else result)
    return r, _extract_evidence(raw, page_texts)


def render_html(result: ResearchResult | Mapping[str, Any] | str | Path,
                page_texts: Mapping[str, str] | None = None) -> str:
    """Render the buyer report as one self-contained HTML document (deterministic).

    ``page_texts`` (source id -> page text) is optional; with it, each citation popover shows
    the quote inside its surrounding text."""
    r, evidence = load_input(result, page_texts)
    title = f"Supplier risk report: {company_name(r)}"
    special = _special_page(r)
    if special is not None:
        return _doc(title, special)
    cit = _Cites(r, evidence)
    ordered = ranked_flags(r)
    reds = [f for f in ordered if f.colour == "red"]
    ambers = [f for f in ordered if f.colour == "amber"]
    greens = [f for f in ordered if f.colour == "green"]
    tone = verdict_tone(r)
    tone_word = {"critical": "Knock-out risk", "red": "Red flags", "amber": "Watch items",
                 "green": "No red flags found", "neutral": "Not enough evidence"}[tone]
    summary = f"<p>{e(r.summary)}</p>" if r.summary else ""
    banner = (f'<div class="banner {tone}" role="status"><span class="sr">{e(tone_word)}. </span>'
              f'<div class="v">{e(r.verdict or tone_word)}</div>{summary}</div>')
    na = not_assessed_areas(r)
    na_html = (f'<p class="small"><strong>Not assessed:</strong> {e(", ".join(AREA_LABELS[a] for a in na))}. '
               'No evidence was found for these areas, so nothing is known about them yet.</p>' if na else "")
    radar = (f'<div class="radarbox"><div class="small muted">Risk profile by area · higher means more risk · '
             f'hollow marker = no score</div>{radar_svg(r)}<div class="sr">{_radar_table(r)}</div></div>')
    steps = "".join(f"<li>{e(s)}</li>" for s in r.next_steps[:CAP_NEXT_STEPS]) or \
        "<li>Continue standard supplier qualification; this report is not a qualification.</li>"
    page1 = (f'<section class="page" aria-label="Page 1: at a glance">{_header(r)}{banner}'
             f'<div class="glance">{_total_block(r)}{radar}</div>{na_html}'
             + _flag_block("Red flags", "red", reds, CAP_P1_RED, "No red flags found in the sources checked.", cit)
             + _flag_block("Watch items", "amber", ambers, CAP_P1_AMBER,
                           "No watch items found in the sources checked.", cit)
             + _flag_block("Strengths", "green", greens, CAP_P1_GREEN,
                           "No strengths recorded from the sources checked.", cit)
             + f'<h2>Next steps for the buyer</h2><ul>{steps}</ul></section>')
    limits = "".join(f"<li>{e(x)}</li>" for x in r.limits) or "<li>Automated public-source research, not " \
        "independent verification or supplier qualification.</li>"
    page2_body = (f'<h2>Risk areas</h2>{_area_table(r, cit)}{_timeline_block(r)}{_dug_into(r, cit)}'
                  f'{_method(r)}<h2>Limits of this report</h2><ul class="small">{limits}</ul>')
    # Sources last: their numbering must include every citation made above.
    page2 = (f'<section class="page" aria-label="Page 2: detail"><div class="small muted">{e(company_name(r))} · '
             f'researched {e(r.researched_at[:10])} · page 2 · laid out by code from the research data, '
             f'not by AI</div>{page2_body}{_sources(r, cit)}</section>')
    return _doc(title, page1 + page2)


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
