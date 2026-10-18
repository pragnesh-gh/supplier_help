"""Deterministic Markdown report rendered from a ResearchResult. No model writes the layout.

Same sections, same order and same wording as the HTML report: both draw from
``report_data.report_sections`` (structure of BAFA's risk-analysis guide, all six areas).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .models import ResearchResult
from .report_data import build_sections
from .report_html import Evidence

UNVERIFIED_MARK = "🟨"
UNVERIFIED_TEXT = "not in our trusted source list"
TRUSTED_MARK = "✅"
GLYPH = {"red": "🔴", "amber": "🟡", "green": "🟢", "neutral": "⚪"}
STATUS_GLYPH = {"red": "🔴", "amber": "🟡", "green": "🟢", "context": "⚪", "not_assessed": "⚪"}
ROW_GLYPH = {"checked": "🟢", "context": "⚪", "not_assessed": "⚪", "pointer": "⚪"}

_MD_SPECIAL = re.compile(r"([\\`*_\[\]<>|#])")


def esc(text: str) -> str:
    """Escape Markdown/HTML so fetched titles or summaries cannot inject links or markup."""
    return _MD_SPECIAL.sub(r"\\\1", " ".join(str(text).split()))


def plural(n: int, singular: str, plural_form: str | None = None) -> str:
    """'1 source', '2 sources'; pass plural_form for irregular words."""
    return f"{n} {singular if n == 1 else (plural_form or singular + 's')}"


def report_word_count(md: str) -> int:
    text = re.sub(r"https?://\S+", "URL", md)
    text = re.sub(r"[|#*\-]+", " ", text)
    return len(text.split())


def _cites(cites: list[Mapping[str, Any]]) -> str:
    nums: list[str] = []
    for c in cites:
        n = f"[{c['id']}]" + (UNVERIFIED_MARK if c.get("trust") == "unverified" else "")
        if n not in nums:
            nums.append(n)
    return " ".join(nums)


def _score(a: Mapping[str, Any]) -> str:
    return f"{a['score']} · {a['level']}" if a.get("score") is not None else f"_{a.get('no_score') or 'Not assessed'}_"


def _item(i: Mapping[str, Any], with_area: bool = False) -> str:
    kind = i.get("kind", "finding")
    glyph = ROW_GLYPH.get(str(kind)) or GLYPH.get(str(i.get("colour")), "⚪")
    rid = f"**{i['risk_id']}** " if i.get("risk_id") else ""
    when = (f" ({esc(i['date'])})" if i.get("date") else " (date not stated)") if i.get("flag_id") else ""
    area = f" · {esc(i['area_label'])}" if with_area and i.get("area_label") else ""
    tags = f" ({', '.join(esc(t) for t in i['tags'])})" if i.get("tags") else ""
    return f"- {glyph} {rid}**{esc(i.get('label') or '')}:** {esc(i.get('summary') or '')}{when}{area}{tags} " \
           f"{_cites(list(i.get('cites') or []))}".rstrip()


def _h2(s: Mapping[str, Any]) -> list[str]:
    return [f"## {s['number']}. {s['title']}", ""]


def _render(sections: list[dict[str, Any]], r: ResearchResult) -> str:
    by = {s["id"]: s for s in sections}
    L: list[str] = []
    h = by["header"]
    L += [f"# {esc(h['company'])}", "", "Supplier risk report, structured after BAFA’s risk-analysis guide", ""]
    if h.get("searched_as"):
        L += [f"Searched as “{esc(h['searched_as'])}”", ""]
    L += [" · ".join(f"**{f['label']}:** {esc(f['value'])}" for f in h["fields"]), ""]
    L += [f"> **{esc(n)}**" for n in h["notices"]] + ([""] if h["notices"] else [])

    if r.status == "needs_clarification" and r.clarification:
        L += ["**We need one detail before researching.**", "", esc(r.clarification.question), ""]
        if r.clarification.candidates:
            L += ["| Company | Country | Website |", "| --- | --- | --- |"]
            for c in r.clarification.candidates:
                L.append(f"| {esc(c.legal_name)} | {esc(c.country_name or c.country_code or '—')} | "
                         f"{esc(c.website or '—')} |")
            L.append("")
        return "\n".join(L).rstrip() + "\n"
    if r.status == "error":
        L += [f"> **Research failed:** {esc('; '.join(r.warnings) or 'unknown error')}", ""]
        return "\n".join(L).rstrip() + "\n"

    s = by["summary"]
    L += _h2(s)
    L += [f"**{esc(s['verdict'])}**", ""]
    if s.get("text"):
        L += [esc(s["text"]), ""]
    L += [f"**Total risk score (0–100):** {esc(s['total']['text'])} {esc(s['total']['bands'])}.", ""]
    L += ["| Risk area | Score · level |", "| --- | --- |"]
    L += [f"| {esc(a['label'])} | {_score(a)} |" for a in s["areas"]]
    L.append("")
    L += [f"**Override:** {esc(o)}" for o in s.get("overrides") or []] + ([""] if s.get("overrides") else [])
    L += ["**Most important findings**", ""]
    if s.get("no_findings"):
        L.append(esc(s["no_findings"]))
    L += [_item(i, with_area=True) for i in s["key_findings"]]
    L.append("")
    if s["not_assessed"]:
        L += [f"**Not assessed:** {esc(', '.join(s['not_assessed']))}. No verified facts were found for these areas.",
              ""]

    s = by["profile"]
    L += _h2(s) + ["| Field | Value |", "| --- | --- |"]
    for f in s["fields"]:
        val = esc(f["value"]) if f["state"] == "found" else f"_{esc(f['value'])}_"
        L.append(f"| {f['label']} | {val} {_cites(list(f['cites']))} |".replace("  |", " |"))
    L.append("")

    s = by["country_sector"]
    L += _h2(s) + [f"Country: **{esc(s['country'])}** · Country & Location score: {_score(s['area_score'])}", ""]
    if s["indicators"]:
        L += ["| Indicator | Value | Year | Reading | Source |", "| --- | --- | --- | --- | --- |"]
        L += [f"| {esc(i['label'])} | {esc(i['value'])} | {i.get('year') or ''} | {esc(i['band']) or '—'} | "
              f"{_cites(list(i['cites']))} |" for i in s["indicators"]]
    else:
        L.append("_No country index data found._")
    L += ["", f"**{s['sector']['label']}:** _{s['sector']['value']}_. {esc(s['sector']['note'])}", ""]

    s = by["company_risks"]
    L += _h2(s)
    for a in s["areas"]:
        L += [f"### {STATUS_GLYPH[a['status']]} {esc(a['label'])} · {a['status_label']} · score {_score(a['score'])}", ""]
        L += [_item(i) for i in a["rows"]]
        L.append("")
    tl = s["timeline"]
    L += ["**Event timeline** (oldest first)", ""]
    L += [f"- {esc(ev['date'] or '')} · {esc(ev['area_label'])} · {ev['label']}: {esc(ev['summary'])}"
          for ev in tl["events"]] or ["No dated findings in the sources checked."]
    if tl["undated"]:
        L.append(f"- {plural(int(tl['undated']), 'finding')} without a date not shown.")
    L.append("")

    s = by["weighting"]
    L += _h2(s) + ["| Risk area | Score · level | Weight |", "| --- | --- | --- |"]
    L += [f"| {esc(a['label'])} | {_score(a)} | {str(a['weight_pct']) + '%' if a.get('weight_pct') is not None else '—'} |"
          for a in s["areas"]]
    t = s["total"]
    L.append(f"| **Total** | {t['score']} · {t['level']} | 100% |" if t.get("score") is not None
             else f"| **Total** | _{t.get('no_total')}_ | |")
    L += ["", "**Likelihood and severity** (risk codes from the register)", ""]
    hm = s["heatmap"]
    L.append("| Severity \\ Likelihood | " + " | ".join(c["label"] for c in hm["columns"]) + " |")
    L.append("| --- |" + " --- |" * len(hm["columns"]))
    for row in hm["rows"]:
        cells = [(", ".join(x["risk_id"] for x in c["risks"]) or "—") + f" ({c['priority_label']})" for c in row["cells"]]
        L.append(f"| **{row['label']}** | " + " | ".join(cells) + " |")
    L.append("")
    L += [f"- **{b['label']}:** _{b['value']}_" for b in s["buyer_inputs"]]
    L.append("")

    s = by["register"]
    L += _h2(s)
    if not s["rows"]:
        L += [esc(s["empty"]), ""]
    else:
        L += ["| ID | Risk | Area | Owner | Weighting | Suggested measures |", "| --- | --- | --- | --- | --- | --- |"]
        for x in s["rows"]:
            area_sc = f"{x['area_score']} · {x['area_level']}" if x.get("area_score") is not None else \
                f"_{x.get('area_no_score') or 'Not assessed'}_"
            when = f" ({esc(x['date'])})" if x.get("date") else ""
            tags = f" ({', '.join(esc(t) for t in x['tags'])})" if x["tags"] else ""
            L.append(f"| {x['risk_id']} | {GLYPH[x['colour']]} {esc(x['description'])}{when}{tags} "
                     f"{_cites(list(x['cites']))} | {esc(x['area_label'])} | _{x['owner']}_ | {x['priority_label']}: "
                     f"severity {x['severity']}, likelihood {x['likelihood']}; area score {area_sc} | "
                     f"{' '.join(esc(m) for m in x['measures'])} |")
        L.append("")

    s = by["prevention"]
    L += _h2(s)
    for n, st in enumerate(s["steps"], start=1):
        tied = ", ".join(x["risk_id"] for x in st["risks"])
        L.append(f"{n}. {esc(st['text'])}" + (f" (addresses {tied})" if tied else ""))
    L.append("")

    s = by["documentation"]
    L += _h2(s) + ["**How the scores work**", ""]
    L += [f"- {esc(m)}" for m in s["method"]]
    if s["weights"]:
        L.append("- Area weights: " + ", ".join(f"{esc(w['label'])} {w['pct']}%" for w in s["weights"]) + ".")
    if s.get("total_method"):
        L.append(f"- Total in this report: {esc(s['total_method'])}.")
    hr = s["heatmap_rule"]
    L += ["", "**Heatmap rule**", "", esc(hr["note"]) + " Rules are read top to bottom; the first that fits applies.", ""]
    L += [f"- Severity: {esc(c)} → {v}" for c, v in hr["severity"]]
    L += [f"- Likelihood: {esc(c)} → {v}" for c, v in hr["likelihood"]]
    bd = s["breakdown"]
    L += ["", "**How each fact was scored**", "", esc(bd["note"]), ""]
    for a in bd["areas"]:
        L.append(f"- **{esc(a['label'])}**: {_score(a)}")
        for sub in a["sub_scores"]:
            sc = sub["score"] if sub.get("score") is not None else f"_{esc(sub.get('not_assessed') or 'Not assessed')}_"
            L.append(f"  - {esc(sub['label'])}: {sc}")
            for x in sub["lines"]:
                pts = f" = {x['points']:.1f}" if x.get("points") is not None else ""
                L.append(f"    - {esc(x['label'])}{pts}: {esc(x['rule'])} {_cites(list(x['cites']))}".rstrip())
        for x in a["overrides"]:
            L.append(f"  - Override: {esc(x['label'])}: {esc(x['rule'])}")
    for x in bd["total_overrides"]:
        L.append(f"- Total override: {esc(x['label'])}: {esc(x['rule'])}")
    L += ["", "**Follow-up checks**", ""]
    if not s["followups"]:
        L.append("No follow-up searches were needed: no red flag or watch item called for a deeper check.")
    for fu in s["followups"]:
        on = f" (on {fu['risk_id']})" if fu.get("risk_id") else ""
        L.append(f"- **{esc(fu['question'])}**{on} {esc(fu['outcome'])} {_cites(list(fu['cites']))}".rstrip())
    L += ["", "**Limits of this report**", ""]
    L += [f"- {esc(x)}" for x in s["limits"]]
    L += ["", "**Sources**", "", f"{TRUSTED_MARK} on our trusted source list · {UNVERIFIED_MARK} {UNVERIFIED_TEXT}", ""]
    if not s["sources"]:
        L.append("No sources cited.")
    for src in s["sources"]:
        quotes = "".join(f" “{esc(q)}”" for q in src["quotes"])
        L.append(f"{src['num']}. {src['trust_label']} · {esc(src['title'])} — {esc(src['publisher'])}, "
                 f"{src['published'] or 'date not stated'} (accessed {src['accessed']}). <{src['url']}>{quotes}")
    if s["uncited"] > 0:
        L += ["", f"{plural(int(s['uncited']), 'further source')} checked but not cited."]
    f = by["footer"]
    L += ["", "---", "", f"_{esc(f['text'])} Structure source: [{esc(f['link_label'])}]({f['link']})._"]
    return "\n".join(L).rstrip() + "\n"


def render_markdown(result: ResearchResult, page_texts: Mapping[str, str] | None = None) -> str:
    """Render the buyer report in the fixed section order. Flag lists are never trimmed."""
    return _render(build_sections(result, Evidence(page_texts=dict(page_texts or {}))), result)
