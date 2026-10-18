"""Deterministic Markdown report rendered from a ResearchResult. No model writes the layout."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .dates import normalize_date
from .models import AreaScore, Flag, ResearchResult, Source
from .rules import sort_flags

SYMBOL = {"red": "🔴", "amber": "🟡", "green": "🟢", "not_assessed": "⚪"}
STATUS_TEXT = {"red": "🔴 Red flag", "amber": "🟡 Watch", "green": "🟢 No issues found", "context": "⚪ Context only",
               "not_assessed": "⚪ Not assessed"}
CONTEXT_OLD_TEXT = "⚪ Context: older or resolved matter"
# Source marks. A square, not a circle: the circles already mean flag colours (🟡 = watch item).
UNVERIFIED_MARK = "🟨"
UNVERIFIED_TEXT = "not in our trusted source list"
TRUSTED_MARK = "✅"
COVERAGE_TEXT = {"not_assessed": "no evidence"}  # otherwise the cell counts the pages that backed the area
TARGET_WORDS = 650
HARD_CAP_WORDS = 1000

_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>|#])")


def esc(text: str) -> str:
    """Escape Markdown/HTML so fetched titles or summaries cannot inject links or markup."""
    return _MD_SPECIAL.sub(r"\\\1", " ".join(text.split()))


def plural(n: int, singular: str, plural_form: str | None = None) -> str:
    """'1 source', '2 sources'; pass plural_form for irregular words."""
    return f"{n} {singular if n == 1 else (plural_form or singular + 's')}"


def report_word_count(md: str) -> int:
    text = re.sub(r"https?://\S+", "URL", md)
    text = re.sub(r"[|#*\-]+", " ", text)
    return len(text.split())


# Flag lists are never shortened to save words; only these caps apply.
CAP_RED, CAP_AMBER, CAP_GREEN = 5, 5, 3


@dataclass
class _Compact:
    """Word-budget trimming outside the flag lists, applied step by step."""
    table_refs_only: bool = False  # table rows that repeat a listed flag show a short pointer instead


class _Citations:
    def __init__(self, sources: list[Source]) -> None:
        self.by_id = {s.id: s for s in sources}
        self.order: list[str] = []

    def cite(self, source_ids: list[str], long_mark: bool = False) -> str:
        """'[1] [2]'; a citation of an unverified site gets the 🟨 mark (with its meaning if long_mark)."""
        nums = []
        unverified = False
        for sid in source_ids:
            if sid not in self.by_id:
                continue
            if sid not in self.order:
                self.order.append(sid)
            nums.append(self.order.index(sid) + 1)
            unverified = unverified or self.by_id[sid].trust == "unverified"
        text = " ".join(f"[{n}]{UNVERIFIED_MARK if self.by_id[self.order[n - 1]].trust == 'unverified' else ''}"
                        for n in sorted(set(nums)))
        if unverified and long_mark:
            text += f" {UNVERIFIED_TEXT}"
        return text


def _date_part(f: Flag) -> str:
    return f" ({f.event_date})" if f.event_date else ""


def _flag_line(f: Flag, cit: _Citations) -> str:
    tags = []
    if f.claim_status == "alleged":
        tags.append("alleged")
    if f.company_stated:
        tags.append("company-stated")
    if f.stale:
        tags.append("older event")
    if f.trust == "unverified":
        tags.append("unverified source only" + (", capped at watch item" if f.capped_unverified else ""))
    tag = f" ({', '.join(tags)})" if tags else ""
    return f"- {esc(f.summary)}{_date_part(f)}{tag} {cit.cite(f.source_ids, long_mark=True)}".rstrip()


def _flag_section(
    title: str, flags: list[Flag], cap: int, empty: str, noun: tuple[str, str], cit: _Citations
) -> list[str]:
    out = [f"## {title}", ""]
    if not flags:
        out.append(empty)
    for f in flags[:cap]:
        out.append(_flag_line(f, cit))
    hidden = len(flags) - cap
    if hidden > 0:
        out += ["", f"_+{plural(hidden, 'lower-priority ' + noun[0], 'lower-priority ' + noun[1])} not shown (in full data)._"]
    out.append("")
    return out


def _render(r: ResearchResult, compact: _Compact) -> str:
    cit = _Citations(r.sources)
    L: list[str] = []
    name = r.entity.legal_name if r.entity else r.company_input
    L.append(f"# Supplier risk research: {esc(name)}")
    L.append("")
    meta = []
    if r.entity:
        meta.append(esc(r.entity.country_name or r.entity.country_code or "country unknown"))
        meta.append(esc(r.entity.website or "website unknown"))
    meta.append(f"researched {r.researched_at[:10]}")
    meta.append(f"{plural(r.stats.pages_read, 'source')} checked")
    L.append(" · ".join(meta))
    L.append("")
    if r.notice:
        L += [f"> **{esc(r.notice)}**", ""]
    if r.status == "partial":
        L += ["> **Partial result:** the run stopped early (time or budget limit). Some areas may be incomplete.", ""]
    if r.status == "error":
        L += [f"> **Research failed:** {esc('; '.join(r.warnings) or 'unknown error')}", ""]

    if r.status == "needs_clarification" and r.clarification:
        L += ["**We need one detail before researching.**", "", esc(r.clarification.question), ""]
        if r.clarification.candidates:
            L += ["| Company | Country | Website |", "| --- | --- | --- |"]
            for c in r.clarification.candidates:
                L.append(f"| {esc(c.legal_name)} | {esc(c.country_name or c.country_code or '—')} | {esc(c.website or '—')} |")
            L.append("")
        return "\n".join(L).rstrip() + "\n"

    L += [f"**Verdict: {esc(r.verdict)}**", ""]
    if r.summary:
        L += [esc(r.summary), ""]
    L += [f"**Total risk score (0–100):** {_score_text(r.scores.total, r.scores.total_level)}", ""]

    ordered = sort_flags(r.flags)
    reds = [f for f in ordered if f.colour == "red"]
    ambers = [f for f in ordered if f.colour == "amber"]
    greens = [f for f in ordered if f.colour == "green"]
    shown_ids = {f.id for f in reds[:CAP_RED] + ambers[:CAP_AMBER] + greens[:CAP_GREEN]}
    section_name = {"red": "red flags", "amber": "watch items", "green": "strengths"}

    # -- page 1: at a glance -------------------------------------------------------
    scores = {a.area: a for a in r.scores.areas}
    L += ["## Risk areas", "", "| Area | Status | Score · level · pages used | Finding |", "| --- | --- | --- | --- |"]
    flags_by_id = {f.id: f for f in r.flags}
    for a in r.areas:
        top = flags_by_id.get(a.flag_ids[0]) if a.flag_ids else None
        ref = cit.cite(top.source_ids) if top else ""
        if compact.table_refs_only and top is not None and top.id in shown_ids:
            finding = f"See {section_name[top.colour]} below {ref}"
            more = len([fid for fid in a.flag_ids if fid in shown_ids and flags_by_id[fid].colour == top.colour]) - 1
            if more > 0:
                finding += f" (+{more} more)"
        else:
            finding = esc(a.finding) + (f" {ref}" if ref else "")
        status_text = STATUS_TEXT[a.status]
        if a.status == "context" and top is not None and top.stale:
            status_text = CONTEXT_OLD_TEXT
        if a.status == "context" and top is not None and top.stale:
            finding += f" ({top.event_date[:4] if top.event_date else 'older'})"
        L.append(f"| {esc(a.label)} | {status_text} | {_area_score_cell(scores.get(a.area))} | {finding} |")
    L.append("")

    L += _flag_section("🔴 Red flags", reds, CAP_RED, "No red flags found in the sources checked.",
                       ("red flag", "red flags"), cit)
    L += _flag_section("🟡 Watch items", ambers, CAP_AMBER, "No watch items found in the sources checked.",
                       ("watch item", "watch items"), cit)
    L += _flag_section("🟢 Strengths", greens, CAP_GREEN, "No strengths recorded from the sources checked.",
                       ("strength", "strengths"), cit)

    L += ["## Recommended next steps for the buyer", ""]
    L += [f"- {esc(x)}" for x in r.next_steps[:3]]
    L += ["", "---", ""]

    # -- page 2: details -----------------------------------------------------------
    L += ["## What we dug into", ""]
    if not r.followups:
        L.append("No follow-up searches were needed: no red or watch item warranted a deeper check.")
    for fu in r.followups:
        flag = flags_by_id.get(fu.flag_id)
        what = f"{flag.colour.replace('amber', 'watch item').replace('red', 'red flag')} {cit.cite(flag.source_ids)}" if flag else "item"
        refs = cit.cite(fu.corroborating_source_ids)
        L.append(f"- **{esc(fu.question)}** (on {what.strip()}) {esc(fu.outcome)} {refs}".rstrip())
    L.append("")

    L += ["## How to read this report", ""]
    L.append(f"- Sources: {TRUSTED_MARK} = on our trusted source list. {UNVERIFIED_MARK} = {UNVERIFIED_TEXT} "
             "(an unverified site): a fact found only there is at most a watch item and never a knock-out, "
             "until a trusted source confirms it.")
    L.append(f"- Scores: 0–100, higher = more risk (scale of the challenge dataset); Low 0–24, Medium 25–49, High 50–74, Critical 75–100. "
             f"Method: {esc(r.scores.total_method)}. An area with no evidence is never scored.")
    L.append("")

    L += ["## Limits of this report", ""]
    L += [f"- {esc(x)}" for x in r.limits]
    L.append("")

    L += ["## Sources", ""]
    if not cit.order:
        L.append("No sources cited.")
    for i, sid in enumerate(cit.order, start=1):
        s = cit.by_id[sid]
        pub = normalize_date(s.published_date) or "date not stated"
        if s.trust == "unverified":
            mark = f"{UNVERIFIED_MARK} {UNVERIFIED_TEXT}"
        else:
            mark = f"{TRUSTED_MARK} trusted" + (", company-stated" if s.tier == "company_own" else "")
        L.append(f"{i}. {mark} · {esc(s.title)} — {esc(s.publisher)}, {pub} (accessed {s.retrieved_at[:10]}). <{s.url}>")
    uncited = len(r.sources) - len(cit.order)
    if uncited > 0:
        verb = "is" if uncited == 1 else "are"
        L += ["", f"{plural(uncited, 'further source')} checked {verb} in the full data."]
    return "\n".join(L).rstrip() + "\n"


def _score_text(score: int | None, level: str | None) -> str:
    return f"{score} · {level}" if score is not None else "— (not scored yet)"


def _area_score_cell(a: AreaScore | None) -> str:
    if a is None:
        return "—"
    parts = []
    if a.trusted_pages:
        parts.append(plural(a.trusted_pages, "trusted page"))
    if a.unverified_pages:
        parts.append(f"{UNVERIFIED_MARK} {plural(a.unverified_pages, 'unverified page')}")
    cov = " + ".join(parts) or COVERAGE_TEXT["not_assessed"]
    if a.score is None:
        return f"— · {cov}"
    return f"{a.score} · {a.level or '—'} · {cov}"


def render_markdown(result: ResearchResult) -> str:
    """Render the buyer report. Flag lists are never trimmed; if the report runs long,
    risk-table rows that repeat a listed flag are shortened to a pointer instead."""
    md = _render(result, _Compact())
    if report_word_count(md) > TARGET_WORDS:
        md = _render(result, _Compact(table_refs_only=True))
    return md
