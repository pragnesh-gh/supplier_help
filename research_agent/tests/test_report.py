import re

from research_agent.models import (
    UMBRELLAS,
    AreaStatus,
    ClarificationRequest,
    ConfirmedEntity,
    Flag,
    Followup,
    ResearchResult,
    RunStats,
    Source,
)
from research_agent.report import render_markdown, report_word_count

LABELS = {"financial": "Financial", "legal": "Legal & Compliance", "country": "Country & Location",
          "people": "People & Safety", "operations": "Operations & Quality", "reputation": "Reputation"}


def _src(i, tier="major_news"):
    return Source(id=f"S{i}", url=f"https://www.reuters.com/a{i}", title=f"Title {i}", publisher="Reuters",
                  tier=tier, published_date="2026-01-0" + str(1 + i % 9), retrieved_at="2026-10-18",
                  found_by="legal-1", umbrella="legal")


def _flag(i, colour, area="legal", src=1, knockout=False, company_stated=False):
    return Flag(id=f"F{i}", colour=colour, area=area, event_type="regulatory_fine", severity="high",
                claim_status="confirmed", summary=f"Summary {i} of a {colour} item.", quote="q",
                event_date=f"2026-0{1 + i % 9}", source_ids=[f"S{src}"], knockout=knockout,
                company_stated=company_stated)


def _result(n_red=2, n_amber=2, n_green=1, n_sources=6, followups=True):
    sources = [_src(i) for i in range(1, n_sources + 1)]
    flags = []
    k = 0
    for colour, n in (("red", n_red), ("amber", n_amber), ("green", n_green)):
        for _ in range(n):
            k += 1
            flags.append(_flag(k, colour, src=1 + (k % n_sources)))
    areas = []
    for a in UMBRELLAS:
        st = "red" if a == "legal" and n_red else ("not_assessed" if a == "reputation" else "green")
        areas.append(AreaStatus(area=a, label=LABELS[a], status=st,
                                finding="Summary 1 of a red item." if st == "red" else
                                ("Not assessed — no trusted source returned evidence." if st == "not_assessed"
                                 else "No issues found in the sources checked."),
                                flag_ids=["F1"] if st == "red" else [], pages_checked=0 if st == "not_assessed" else 2))
    fus = [Followup(id="followup-1", flag_id="F1", flag_summary="Summary 1", question="Was the fine appealed?",
                    query="q", pages_checked=1, corroborating_source_ids=["S2"],
                    outcome="Found 1 more supporting source.")] if followups else []
    return ResearchResult(
        status="ok", company_input="Veltrava", researched_at="2026-10-18T10:00:00+00:00",
        entity=ConfirmedEntity(legal_name="Veltrava Rail Components GmbH", country_code="DE",
                               country_name="Germany", website="veltrava-rail.example"),
        verdict="Red flags — review before shortlisting", summary="Two sentences. Of summary.",
        flags=flags, areas=areas, followups=fus, next_steps=["Step one.", "Step two."],
        limits=["Limit one."], sources=sources, stats=RunStats(pages_read=n_sources),
    )


def test_has_all_sections_in_order():
    md = render_markdown(_result())
    order = ["# Supplier risk research: Veltrava Rail Components GmbH", "**Verdict:", "**Total risk score",
             "## Risk areas", "## 🔴 Red flags", "## 🟡 Watch items", "## 🟢 Strengths", "## Recommended next steps",
             "\n---\n", "## What we dug into", "## How to read this report", "## Limits of this report", "## Sources"]
    pos = [md.find(h) for h in order]
    assert all(p >= 0 for p in pos), list(zip(order, pos))
    assert pos == sorted(pos)


def test_header_line_has_country_website_date_and_source_count():
    md = render_markdown(_result())
    line = md.splitlines()[2]
    assert "Germany" in line and "veltrava-rail.example" in line and "2026-10-18" in line and "6 sources" in line


def test_risk_table_has_six_rows_and_status_symbols():
    md = render_markdown(_result())
    rows = [ln for ln in md.splitlines() if ln.startswith("| ") and not ln.startswith("| Area") and "---" not in ln]
    assert len(rows) == 6
    assert any("⚪ Not assessed" in r for r in rows)
    assert any("🔴" in r for r in rows)


def test_citations_are_numbered_in_order_of_first_use_and_all_resolve():
    md = render_markdown(_result())
    body, sources = md.split("## Sources", 1)
    cited = [int(n) for n in re.findall(r"\[(\d+)\]", body)]
    assert cited, "no citations"
    first_seen = list(dict.fromkeys(cited))
    assert first_seen == list(range(1, len(first_seen) + 1))
    listed = [int(n) for n in re.findall(r"^(\d+)\. ", sources, re.MULTILINE)]
    assert listed == list(range(1, len(first_seen) + 1))
    assert "(accessed 2026-10-18)" in sources and "https://www.reuters.com/" in sources


def test_caps_on_flag_lists():
    md = render_markdown(_result(n_red=9, n_amber=9, n_green=9, n_sources=30))
    sec = lambda name: md.split("## " + name, 1)[1].split("\n## ", 1)[0]  # noqa: E731
    md = md.replace("## 🔴 ", "## ").replace("## 🟡 ", "## ").replace("## 🟢 ", "## ")
    assert sec("Red flags").count("\n- ") <= 5
    assert sec("Watch items").count("\n- ") <= 5
    assert sec("Strengths").count("\n- ") <= 3
    assert "+4 lower-priority red flags not shown (in full data)" in sec("Red flags")
    assert "+4 lower-priority watch items not shown (in full data)" in sec("Watch items")
    assert "+6 lower-priority strengths not shown (in full data)" in sec("Strengths")


def _lists(md):
    md = md.replace("## 🔴 ", "## ").replace("## 🟡 ", "## ").replace("## 🟢 ", "## ")
    return "".join(md.split("## " + n, 1)[1].split("\n## ", 1)[0] for n in ("Red flags", "Watch items", "Strengths"))


def test_all_flags_listed_when_under_cap():
    r = _result(n_red=5, n_amber=5, n_green=3, n_sources=20)
    md = render_markdown(r)
    lists = _lists(md)
    for f in r.flags:
        assert f.summary in lists, f.id
    assert "not shown" not in md


def test_flags_are_never_trimmed_to_fit_word_budget():
    r = _result(n_red=5, n_amber=5, n_green=3, n_sources=20)
    for f in r.flags:
        f.summary = "A fairly long one-line finding about the supplier that uses up many words in the report " + f.id
    md = render_markdown(r)
    lists = _lists(md)
    assert all(f.summary in lists for f in r.flags)
    assert report_word_count(md) <= 1000


def test_report_never_mentions_result_json():
    for kw in ({}, {"n_red": 9, "n_amber": 9, "n_green": 9, "n_sources": 30}):
        assert "result.json" not in render_markdown(_result(**kw))


def test_no_lazy_plurals_in_report():
    for kw in ({}, {"n_red": 9, "n_amber": 9, "n_green": 9, "n_sources": 30}, {"n_red": 0, "n_amber": 0, "n_green": 0}):
        assert "(s)" not in render_markdown(_result(**kw))


def test_uncited_sources_line_pluralised():
    r = _result()
    r.sources.append(_src(50))
    md = render_markdown(r)
    assert "further source checked is in the full data" in md or "further sources checked are in the full data" in md


def test_length_caps():
    assert report_word_count(render_markdown(_result())) <= 600
    big = render_markdown(_result(n_red=12, n_amber=12, n_green=12, n_sources=40))
    assert report_word_count(big) <= 1000


def test_empty_lists_say_none_found_not_no_risk():
    md = render_markdown(_result(n_red=0, n_amber=0, n_green=0, followups=False))
    assert "No red flags found in the sources checked" in md
    assert "no risk" not in md.lower()
    assert "No follow-up searches were needed" in md


def test_company_stated_label():
    r = _result()
    r.flags[-1].company_stated = True
    assert "(company-stated)" in render_markdown(r)


def test_needs_clarification_report():
    r = ResearchResult(status="needs_clarification", company_input="Veltrava", researched_at="2026-10-18T10:00:00+00:00",
                       clarification=ClarificationRequest(question="Which one?", candidates=[
                           ConfirmedEntity(legal_name="A GmbH", country_name="Germany", website="a.example"),
                           ConfirmedEntity(legal_name="B Ltd", country_name="Australia", website="b.example")]))
    md = render_markdown(r)
    assert "Which one?" in md and "A GmbH" in md and "B Ltd" in md


def test_notice_banner_shown():
    r = _result()
    r.notice = "FIXTURE DATA"
    assert "FIXTURE DATA" in render_markdown(r).split("\n## ", 1)[0]


def test_markdown_injection_in_titles_is_escaped():
    r = _result()
    r.sources[0].title = "Evil](https://evil.example) <script>x</script>"
    md = render_markdown(r)
    assert "<script>" not in md
    assert "](https://evil.example)" not in md


def test_unverified_source_gets_yellow_marker_inline_and_in_sources():
    r = _result()
    r.sources[1].trust = "unverified"
    r.sources[1].tier = "open_web"
    r.sources[1].publisher = "blog.example"
    r.flags[0].source_ids = ["S2"]
    r.flags[0].trust = "unverified"
    md = render_markdown(r)
    body, sources = md.split("## Sources", 1)
    line = next(ln for ln in body.splitlines() if ln.startswith("- ") and r.flags[0].summary in ln)
    assert "🟨 not in our trusted source list" in line and "unverified source only" in line
    src_line = next(ln for ln in sources.splitlines() if "blog.example" in ln)
    assert src_line.split(" ", 1)[1].startswith("🟨 not in our trusted source list")
    trusted_lines = [ln for ln in sources.splitlines() if re.match(r"^\d+\. ", ln) and "blog.example" not in ln]
    assert trusted_lines and all("✅ trusted" in ln for ln in trusted_lines)


def test_trusted_only_report_has_no_yellow_marker():
    assert "🟨 not in our trusted source list ·" not in render_markdown(_result())


def test_first_page_has_total_and_area_score_placeholders():
    from research_agent.scoring import score_result
    r = _result()
    r.scores = score_result(r.flags, r.areas)
    md = render_markdown(r)
    page1, page2 = md.split("\n---\n", 1)
    assert "**Total risk score (0–100):** — (not scored yet)" in page1
    rows = [ln for ln in page1.splitlines() if ln.startswith("| ") and "---" not in ln and not ln.startswith("| Area")]
    assert len(rows) == 6 and all("— · " in r for r in rows)
    assert any("— · no evidence" in r for r in rows)  # not-assessed area is never scored 0
    assert "Method: not scored yet" in page2 and "Method:" not in page1
    assert "## Sources" in page2 and "## Red flags" not in page2.replace("🔴 ", "")


def test_rfc2822_source_dates_are_shown_as_iso():
    r = _result()
    for src in r.sources:
        src.published_date = "Wed, 29 Jul 2026 00:00:00 GMT"
    md = render_markdown(r)
    assert "Wed, 29 Ju" not in md
    assert "2026-07-29 (accessed" in md
