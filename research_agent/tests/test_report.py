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
from research_agent.report import render_markdown

LABELS = {"financial": "Financial", "legal": "Legal & Governance", "country": "Country & Location",
          "people": "People & Safety", "operations": "Operations & Delivery", "reputation": "Reputation & Outside View"}


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


HEADINGS = ["## 1. Summary for decision makers", "## 2. Supplier profile", "## 3. Country and sector risk",
            "## 4. Company-specific risks found", "## 5. Weighting and prioritisation", "## 6. Risk register",
            "## 7. From priority risks to prevention", "## 8. Documentation"]


def test_has_all_sections_in_fixed_order():
    for kw in ({}, {"n_red": 0, "n_amber": 0, "n_green": 0, "followups": False}):
        md = render_markdown(_result(**kw))
        pos = [md.find(h) for h in ["# Veltrava Rail Components GmbH", *HEADINGS, "not a legal LkSG risk analysis"]]
        assert all(p >= 0 for p in pos), pos
        assert pos == sorted(pos)


def test_area_order_in_section_4_is_fixed():
    md = render_markdown(_result())
    sec4 = md.split(HEADINGS[3], 1)[1].split(HEADINGS[4], 1)[0]
    order = ["Operations & Delivery", "Financial", "People & Safety", "Legal & Governance", "Country & Location",
             "Reputation & Outside View"]
    pos = [sec4.find(f" {o} · ") for o in order]
    assert all(p >= 0 for p in pos) and pos == sorted(pos)


def test_header_line_has_country_website_date_and_source_count():
    md = render_markdown(_result())
    line = next(ln for ln in md.splitlines() if ln.startswith("**Legal entity:**"))
    assert "Germany" in line and "veltrava-rail.example" in line and "2026-10-18" in line
    assert "**Sources checked:** 6" in line


def test_not_assessed_area_is_never_zero():
    md = render_markdown(_result())
    rows = [ln for ln in md.splitlines() if ln.startswith("| Reputation")]
    assert rows and all("_Not assessed_" in r or "_not scored yet_" in r for r in rows)
    assert all("| 0 " not in r for r in rows)


def test_citations_are_numbered_in_order_of_first_use_and_all_resolve():
    md = render_markdown(_result())
    body, sources = md.split("**Sources**", 1)
    cited = [int(n) for n in re.findall(r"\[(\d+)\]", body)]
    assert cited, "no citations"
    first_seen = list(dict.fromkeys(cited))
    assert first_seen == list(range(1, len(first_seen) + 1))
    listed = [int(n) for n in re.findall(r"^(\d+)\. ", sources, re.MULTILINE)]
    assert listed == list(range(1, len(first_seen) + 1))
    assert "(accessed 2026-10-18)" in sources and "https://www.reuters.com/" in sources


def test_every_flag_is_listed_in_section_4_never_trimmed():
    r = _result(n_red=9, n_amber=9, n_green=9, n_sources=30)
    md = render_markdown(r)
    sec4 = md.split(HEADINGS[3], 1)[1].split(HEADINGS[4], 1)[0]
    for f in r.flags:
        assert f.summary in sec4, f.id
    assert "not shown" not in sec4.split("**Event timeline**")[0]


def test_strengths_are_checked_rows_not_a_list():
    md = render_markdown(_result())
    assert "Strengths" not in md.split("**Event timeline**")[0]
    assert "**Checked, nothing adverse found:** Summary 5 of a green item." in md


def test_report_never_mentions_result_json_or_lazy_plurals():
    for kw in ({}, {"n_red": 9, "n_amber": 9, "n_green": 9, "n_sources": 30}, {"n_red": 0, "n_amber": 0, "n_green": 0}):
        md = render_markdown(_result(**kw))
        assert "result.json" not in md and "(s)" not in md and ".yaml" not in md


def test_uncited_sources_line_pluralised():
    r = _result()
    r.sources.append(_src(50))
    md = render_markdown(r)
    assert re.search(r"\n\d+ further sources? checked but not cited\.", md)
    assert "1 further sources" not in md


def test_empty_lists_say_none_found_not_no_risk():
    md = render_markdown(_result(n_red=0, n_amber=0, n_green=0, followups=False))
    assert "No red flags or watch items found in the sources checked" in md
    assert "No red flags or watch items to record." in md
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
    body, sources = md.split("**Sources**", 1)
    line = next(ln for ln in body.splitlines() if ln.startswith("- ") and r.flags[0].summary in ln)
    assert "]🟨" in line and "unverified source only" in line
    src_line = next(ln for ln in sources.splitlines() if "blog.example" in ln)
    assert src_line.split(" ", 1)[1].startswith("🟨 not in our trusted source list")
    trusted_lines = [ln for ln in sources.splitlines() if re.match(r"^\d+\. ", ln) and "blog.example" not in ln]
    assert trusted_lines and all("✅ trusted" in ln for ln in trusted_lines)


def test_unscored_result_shows_placeholders_never_zero():
    from research_agent.scoring import score_result
    r = _result()
    r.scores = score_result(r.flags, r.areas)
    md = render_markdown(r)
    assert "**Total risk score (0–100):** Risk score not scored yet" in md
    sec1 = md.split(HEADINGS[0], 1)[1].split(HEADINGS[1], 1)[0]
    rows = [ln for ln in sec1.splitlines() if ln.startswith("| ") and "---" not in ln and not ln.startswith("| Risk area")]
    assert len(rows) == 6 and all("_" in r for r in rows)
    assert "_Not assessed_" in next(r for r in rows if r.startswith("| Reputation"))


def test_rfc2822_source_dates_are_shown_as_iso():
    r = _result()
    for src in r.sources:
        src.published_date = "Wed, 29 Jul 2026 00:00:00 GMT"
    md = render_markdown(r)
    assert "Wed, 29 Ju" not in md
    assert "2026-07-29 (accessed" in md


def test_markdown_is_deterministic():
    r = _result()
    assert render_markdown(r) == render_markdown(ResearchResult.model_validate_json(r.model_dump_json()))
