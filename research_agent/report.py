"""Deterministic Markdown report rendered from a ResearchResult. No model writes the layout."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Flag, ResearchResult, Source
from .rules import sort_flags

SYMBOL = {"red": "🔴", "amber": "🟡", "green": "🟢", "not_assessed": "⚪"}
STATUS_TEXT = {"red": "🔴 Red flag", "amber": "🟡 Watch", "green": "🟢 No issues found", "not_assessed": "⚪ Not assessed"}
TARGET_WORDS = 600
HARD_CAP_WORDS = 1000

_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>|#])")


def esc(text: str) -> str:
    """Escape Markdown/HTML so fetched titles or summaries cannot inject links or markup."""
    return _MD_SPECIAL.sub(r"\\\1", " ".join(text.split()))


def report_word_count(md: str) -> int:
    text = re.sub(r"https?://\S+", "URL", md)
    text = re.sub(r"[|#*\-]+", " ", text)
    return len(text.split())


@dataclass
class _Caps:
    red: int = 5
    amber: int = 5
    green: int = 3


class _Citations:
    def __init__(self, sources: list[Source]) -> None:
        self.by_id = {s.id: s for s in sources}
        self.order: list[str] = []

    def cite(self, source_ids: list[str]) -> str:
        nums = []
        for sid in source_ids:
            if sid not in self.by_id:
                continue
            if sid not in self.order:
                self.order.append(sid)
            nums.append(self.order.index(sid) + 1)
        return " ".join(f"[{n}]" for n in sorted(set(nums)))


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
    tag = f" ({', '.join(tags)})" if tags else ""
    return f"- {esc(f.summary)}{_date_part(f)}{tag} {cit.cite(f.source_ids)}".rstrip()


def _flag_section(title: str, flags: list[Flag], cap: int, empty: str, cit: _Citations) -> list[str]:
    out = [f"## {title}", ""]
    if not flags:
        out.append(empty)
    for f in flags[:cap]:
        out.append(_flag_line(f, cit))
    if len(flags) > cap:
        out += ["", f"_…and {len(flags) - cap} more in result.json._"]
    out.append("")
    return out


def _render(r: ResearchResult, caps: _Caps) -> str:
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
    meta.append(f"{r.stats.pages_read} sources checked")
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

    ordered = sort_flags(r.flags)
    reds = [f for f in ordered if f.colour == "red"]
    ambers = [f for f in ordered if f.colour == "amber"]
    greens = [f for f in ordered if f.colour == "green"]
    L += _flag_section("🔴 Red flags", reds, caps.red, "No red flags found in the sources checked.", cit)
    L += _flag_section("🟡 Watch items", ambers, caps.amber, "No watch items found in the sources checked.", cit)
    L += _flag_section("🟢 Strengths", greens, caps.green, "No strengths recorded from the sources checked.", cit)

    L += ["## Risk areas", "", "| Area | Status | Finding |", "| --- | --- | --- |"]
    flags_by_id = {f.id: f for f in r.flags}
    for a in r.areas:
        src_ids: list[str] = []
        if a.flag_ids and a.flag_ids[0] in flags_by_id:
            src_ids = flags_by_id[a.flag_ids[0]].source_ids
        ref = cit.cite(src_ids)
        finding = esc(a.finding) + (f" {ref}" if ref else "")
        L.append(f"| {esc(a.label)} | {STATUS_TEXT[a.status]} | {finding} |")
    L.append("")

    L += ["## What we dug into", ""]
    if not r.followups:
        L.append("No follow-up searches were needed: no red or watch item warranted a deeper check.")
    for fu in r.followups:
        flag = flags_by_id.get(fu.flag_id)
        what = f"{flag.colour.replace('amber', 'watch item').replace('red', 'red flag')} {cit.cite(flag.source_ids)}" if flag else "item"
        refs = cit.cite(fu.corroborating_source_ids)
        L.append(f"- **{esc(fu.question)}** (on {what.strip()}) {esc(fu.outcome)} {refs}".rstrip())
    L.append("")

    L += ["## Limits of this report", ""]
    L += [f"- {esc(x)}" for x in r.limits]
    L.append("")

    L += ["## Recommended next steps for the buyer", ""]
    L += [f"- {esc(x)}" for x in r.next_steps[:3]]
    L.append("")

    L += ["## Sources", ""]
    if not cit.order:
        L.append("No sources cited.")
    for i, sid in enumerate(cit.order, start=1):
        s = cit.by_id[sid]
        pub = s.published_date[:10] if s.published_date else "date not stated"
        label = " (company-stated)" if s.tier == "company_own" else ""
        L.append(f"{i}. {esc(s.title)} — {esc(s.publisher)}{label}, {pub} (accessed {s.retrieved_at[:10]}). <{s.url}>")
    uncited = len(r.sources) - len(cit.order)
    if uncited > 0:
        L += ["", f"{uncited} further checked source(s) are listed in result.json."]
    return "\n".join(L).rstrip() + "\n"


def render_markdown(result: ResearchResult) -> str:
    """Render the buyer report, shrinking lists until it fits the length targets."""
    ladder = [_Caps(5, 5, 3), _Caps(4, 4, 2), _Caps(3, 3, 2), _Caps(3, 2, 1), _Caps(2, 2, 1)]
    md = _render(result, ladder[0])
    for caps in ladder[1:]:
        if report_word_count(md) <= TARGET_WORDS:
            break
        md = _render(result, caps)
    return md
