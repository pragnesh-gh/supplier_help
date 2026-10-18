"""The fixed BAFA-structured report: section order, empty states, heatmap rule, determinism."""

import json
import re
from pathlib import Path

import pytest

from research_agent.heatmap import describe, likelihood_of, load_rule, severity_of
from research_agent.models import ClarificationRequest, ConfirmedEntity, GradingSignals, ResearchResult
from research_agent.report import render_markdown
from research_agent.report_data import AREA_ORDER, SECTION_IDS, report_sections, section
from research_agent.report_html import render_html
from research_agent.tests.test_report_html import FULL, _flag, _result, _scores, _src
from research_agent.tldr import tldr_data

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
SAMPLE = EXAMPLES / "sample_result.json"
H2 = re.compile(r'<h2 id="sec-(\w+)">')


def _visible_text(html: str) -> str:
    body = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    body = re.sub(r'<a [^>]*href="[^"]*"', "<a", body)
    return re.sub(r"<[^>]+>", " ", body)


@pytest.mark.parametrize("make", [
    lambda: _result(scores=_scores(FULL, total=37, level="Medium")),
    lambda: _result(flags=[], sources=[]),
    lambda: _result(status="partial"),
    lambda: _result(status="error", warnings=["key missing"]),
    lambda: _result(status="needs_clarification", clarification=ClarificationRequest(
        question="Which Acme?", candidates=[ConfirmedEntity(legal_name="Acme A")])),
])
def test_sections_always_present_in_fixed_order(make):
    secs = report_sections(make())
    assert tuple(s["id"] for s in secs) == SECTION_IDS
    assert [s["number"] for s in secs[:-1]] == list(range(9))
    json.dumps(secs, ensure_ascii=False)  # plain data, ready for the web app


def test_html_sections_in_fixed_order_and_footer():
    html = render_html(SAMPLE)
    assert H2.findall(html) == ["summary", "profile", "country_sector", "company_risks", "weighting", "register",
                                "prevention", "documentation"]
    assert html.index('id="sec-header"') < html.index('id="sec-summary"')
    foot = html[html.index('id="sec-footer"'):]
    assert "not a legal LkSG risk analysis" in foot and "handreichung_risikoanalyse.pdf" in foot
    assert "<script" not in html


def test_area_order_in_section_4_is_fixed():
    secs = report_sections(SAMPLE)
    assert [a["area"] for a in section(secs, "company_risks")["areas"]] == list(AREA_ORDER)
    assert [a["area"] for a in section(secs, "weighting")["areas"]] == list(AREA_ORDER)


def test_not_assessed_is_never_zero():
    vals = dict(FULL)
    vals["reputation"] = (0, "not_assessed")  # hostile input: a 0 score on an area without evidence
    r = _result(scores=_scores(vals, total=30, level="Medium"))
    secs = report_sections(r)
    for sid in ("summary", "weighting"):
        rep = next(a for a in section(secs, sid)["areas"] if a["area"] == "reputation")
        assert rep["score"] is None and rep["level"] is None and rep["no_score"] == "Not assessed"
    html = render_html(r)
    m = re.search(r"<tr><td>Reputation &amp; Outside View</td>(.*?)</tr>", html)
    assert m is not None
    row = m.group(1)
    assert "Not assessed" in row and ">0<" not in row
    md = render_markdown(r)
    assert all("| 0" not in ln for ln in md.splitlines() if ln.startswith("| Reputation"))


def test_not_assessed_area_row_in_section_4():
    secs = report_sections(_result())
    rep = next(a for a in section(secs, "company_risks")["areas"] if a["area"] == "reputation")
    assert rep["status_label"] == "Not assessed"
    assert [x["kind"] for x in rep["rows"]] == ["not_assessed"]


def test_strengths_become_checked_rows():
    r = _result()
    secs = report_sections(r)
    fin = next(a for a in section(secs, "company_risks")["areas"] if a["area"] == "financial")
    row = next(x for x in fin["rows"] if x["flag_id"] == "F4")
    assert row["kind"] == "checked" and row["label"] == "Checked, nothing adverse found" and row["cites"]
    html = render_html(r)
    assert "Strengths</h" not in html  # no separate strengths list


def test_heatmap_rule_table():
    rule = load_rule()
    trusted_corroborated = _flag(1, "red")
    trusted_corroborated.signals = GradingSignals(corroborated_by_trusted=True, independent_domains=2)
    single = _flag(2, "amber")
    firsthand = _flag(3, "amber")
    firsthand.signals = GradingSignals(attribution="firsthand_official")
    low = _flag(4, "amber")
    low.severity = "low"
    alleged = _flag(5, "red")
    alleged.claim_status = "alleged"
    alleged.signals = GradingSignals(corroborated_by_trusted=True, independent_domains=2)
    unverified = _flag(6, "amber", trust="unverified")
    unverified.signals = GradingSignals(independent_domains=3)
    cases = [(trusted_corroborated, "high", "likely"), (single, "medium", "possible"),
             (firsthand, "medium", "likely"), (low, "low", "possible"), (alleged, "high", "possible"),
             (unverified, "medium", "unconfirmed")]
    for f, sev, lik in cases:
        assert (severity_of(f, rule), likelihood_of(f, rule)) == (sev, lik), f.id
    text = describe(rule)
    assert ("Red flag", "High") in text["severity"]
    assert text["likelihood"][0] == ("Found only on sites not in our trusted source list", "Unconfirmed")


def test_heatmap_cells_link_to_register_rows():
    html = render_html(SAMPLE)
    heat = html[html.index('<table class="heat"'):html.index("</table>", html.index('<table class="heat"'))]
    links = re.findall(r'href="#risk-(R\d+)"', heat)
    secs = report_sections(SAMPLE)
    reg = section(secs, "register")["rows"]
    assert sorted(links, key=lambda x: int(x[1:])) == [x["risk_id"] for x in reg]
    for rid in links:
        assert f'<tr id="risk-{rid}">' in html
    for x in reg:
        assert f'<li id="flag-{x["flag_id"]}">' in html  # register links back to section 4
    # placed only red flags and watch items, and every one of them
    flags = json.loads(SAMPLE.read_text())["flags"]
    assert len(reg) == sum(f["colour"] in ("red", "amber") for f in flags)


def test_register_and_prevention_fields():
    secs = report_sections(SAMPLE)
    reg = section(secs, "register")["rows"]
    assert reg[0]["priority"] == min(x["priority"] for x in reg)
    assert all(x["owner"] == "Assigned by buyer" and x["measures"] and x["cites"] for x in reg)
    steps = section(secs, "prevention")["steps"]
    assert 1 <= len(steps) <= 3 and all(s["risks"] for s in steps)
    w = section(secs, "weighting")
    assert {b["value"] for b in w["buyer_inputs"]} == {"Buyer input, not assessed"}
    prof = {f["key"]: f for f in section(secs, "profile")["fields"]}
    assert prof["order_volume"]["value"] == "Buyer input, not assessed"
    assert prof["parent_company"]["value"] == "Not found"


def test_documentation_has_breakdown_with_override_and_sources():
    secs = report_sections(SAMPLE)
    doc = section(secs, "documentation")
    assert doc["breakdown"]["available"]
    legal = next(a for a in doc["breakdown"]["areas"] if a["area"] == "legal")
    assert any(x["kind"] == "override" for x in legal["overrides"])
    assert all(s["trust_label"] and s["accessed"] for s in doc["sources"])
    assert [s["num"] for s in doc["sources"]] == list(range(1, len(doc["sources"]) + 1))


def test_report_is_byte_identical_for_same_input():
    a = render_html(SAMPLE)
    assert a == render_html(json.loads(SAMPLE.read_text()))
    assert a == render_html(ResearchResult.model_validate_json(SAMPLE.read_text()))
    r = ResearchResult.model_validate_json(SAMPLE.read_text())
    assert render_markdown(r) == render_markdown(ResearchResult.model_validate_json(SAMPLE.read_text()))
    assert json.dumps(report_sections(SAMPLE)) == json.dumps(report_sections(SAMPLE))


def test_no_internal_wording_in_visible_text():
    for src in (render_html(SAMPLE), render_markdown(ResearchResult.model_validate_json(SAMPLE.read_text()))):
        text = _visible_text(src) if src.startswith("<!doctype") else src
        for bad in (".yaml", "appendix", "§", "result.json", "docs/", "TODO", "_or_", "Risiken", "Handreichung"):
            assert bad not in text, bad


def test_summary_matches_tldr():
    secs = report_sections(SAMPLE)
    s1 = section(secs, "summary")
    d = tldr_data(SAMPLE)
    assert d["score"]["text"] == s1["total"]["text"]
    assert [x["flag_id"] for x in s1["key_findings"]] == [seg["flag_id"] for seg in d["segments"]
                                                          if seg["kind"] == "flag"]
    assert [seg["text"] for seg in d["segments"] if seg["kind"] == "override"] == s1["overrides"]


def test_sample_markdown_is_current():
    """examples/ must be regenerated (python -m research_agent --fixture) after a report change."""
    r = ResearchResult.model_validate_json(SAMPLE.read_text(encoding="utf-8"))
    assert (EXAMPLES / "sample_report.md").read_text(encoding="utf-8") == render_markdown(r)


def test_unknown_source_flag_is_not_a_key_point():
    r = _result(flags=[_flag(1, "red", src=9), _flag(2, "amber", src=1)], sources=[_src(1)])
    s1 = section(report_sections(r), "summary")
    assert [x["flag_id"] for x in s1["key_findings"]] == ["F2"]
