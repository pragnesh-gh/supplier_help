import json
import re
from pathlib import Path

from research_agent.models import ClarificationRequest, ConfirmedEntity
from research_agent.tests.test_report_html import FULL, HOSTILE, _flag, _result, _scores, _src
from research_agent.tldr import (
    MAX_WORDS,
    render_citation_demo,
    score_explainer,
    tldr,
    tldr_data,
    word_count,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PAGE = ("Bonn, 11 March 2026. The competition authority said Acme Rail GmbH was fined EUR 4.2 million "
        "for price-fixing in rail brake pads. The decision is not yet final.")
QUOTE = "Acme Rail GmbH was fined EUR 4.2 million for price-fixing"


def _cited_result(**kw):
    flags = [_flag(1, "red", src=1, quote=QUOTE, summary="Fined EUR 4.2 million for price-fixing; not yet final.",
                   date="2026-03-11"),
             _flag(2, "amber", area="operations", src=2, summary="Recall of 1,800 door actuators.", date="2026-08")]
    return _result(flags=flags, sources=[_src(1), _src(2)], **kw)


def _words(s):
    return [w.casefold() for w in re.findall(r"\w+", s)]


def test_tldr_content_and_length_scored():
    r = _cited_result(scores=_scores(FULL, total=37, level="Medium"))
    d = tldr_data(r, report_url="https://reports.example/acme")
    text = d["text"]
    assert d["word_count"] <= MAX_WORDS and word_count(text) == d["word_count"]
    assert text.startswith("Red flags — review before shortlisting.")
    assert "Risk score 37/100 · Medium · coverage 100%." in text
    assert "(2026-03-11) [1]." in text and "(2026-08) [2]." in text
    assert text.endswith("Full report: https://reports.example/acme")
    assert d["score"]["total"] == 37 and d["score"]["coverage_pct"] == 100
    kinds = [c["kind"] for c in d["chips"]]
    assert kinds[:3] == ["verdict", "score", "coverage"] and kinds.count("flag") == 2
    assert tldr(r, "https://reports.example/acme") == text


def test_tldr_no_score_path_and_gaps():
    d = tldr_data(_cited_result())
    assert "not scored yet" in d["text"]
    assert d["score"]["total"] is None and d["score"]["scored"] is False
    assert "Not assessed: Country & Location, People & Safety, Reputation & Outside View." in d["text"]
    assert d["not_assessed"] == ["Country & Location", "People & Safety", "Reputation & Outside View"]
    assert "no risk" not in d["text"].lower()


def test_tldr_stays_short_with_long_flags():
    long = " ".join(["word"] * 25)
    flags = [_flag(i, "red", src=1, summary=f"{long} {i}.", quote=f"quote {i} words here") for i in range(1, 7)]
    d = tldr_data(_result(flags=flags, sources=[_src(1)]), report_url="https://reports.example/x")
    assert d["word_count"] <= MAX_WORDS
    assert any(s["kind"] == "flag" for s in d["segments"])


def test_every_fact_sentence_is_cited_and_ids_resolve():
    for r in (_cited_result(), _result(flags=[_flag(1, "green", src=1)], sources=[_src(1)], verdict="No red flags found in the sources checked")):
        d = tldr_data(r)
        ids = {c["id"] for c in d["citations"]}
        facts = [s for s in d["segments"] if s["kind"] == "flag"]
        assert facts
        for s in facts:
            assert s["citations"] and set(s["citations"]) <= ids
        for n in ids:
            assert f"[{n}]" in d["text"]


def test_citation_quote_sits_in_excerpt_at_offsets():
    d = tldr_data(_cited_result(), page_texts={"S1": "Intro. " * 60 + PAGE + " Outro." * 60})
    c = d["citations"][0]
    assert c["context_found"] is True and c["quote"] == QUOTE
    assert _words(c["excerpt"][c["quote_start"]:c["quote_end"]]) == _words(QUOTE)
    assert len(c["excerpt"]) <= len(QUOTE) + 2 * 200 + 10
    assert c["link"] == ("https://www.reuters.com/a1#:~:text=Acme%20Rail%20GmbH%20was,"
                         "4.2%20million%20for%20price%2Dfixing")
    assert c["trust"] == "trusted" and c["published"] == "2026-03-02" and c["accessed"] == "2026-10-18"


def test_citation_without_page_text_falls_back_to_quote():
    c = tldr_data(_cited_result())["citations"][0]
    assert c["context_found"] is False
    assert c["excerpt"] == QUOTE and (c["quote_start"], c["quote_end"]) == (0, len(QUOTE))


def test_trust_labels_in_citations():
    flags = [_flag(1, "amber", src=3, trust="unverified"), _flag(2, "red", src=4)]
    srcs = [_src(3, trust="unverified", tier="open_web"), _src(4, tier="company_own")]
    d = tldr_data(_result(flags=flags, sources=srcs))
    trust = {c["source_id"]: c["trust_label"] for c in d["citations"]}
    assert trust["S3"].startswith("🟨") and "company-stated" in trust["S4"]


def test_hostile_quote_is_safe_in_demo_and_report():
    flags = [_flag(1, "red", src=1, quote=HOSTILE + "</script>", summary=HOSTILE)]
    r = _result(flags=flags, sources=[_src(1, title=HOSTILE)])
    page = render_citation_demo(r)
    data_block = page[page.index("/*TLDR_DATA_START*/"):page.index("/*TLDR_DATA_END*/")]
    assert "</script>" not in data_block and "<script>" not in data_block and "<img" not in data_block
    payload = json.loads(data_block.removeprefix("/*TLDR_DATA_START*/"))
    assert payload["tldr"]["citations"][0]["quote"].startswith("<script>")  # intact as data, rendered via textContent
    assert "#:~:text=%3Cscript%3E" in payload["tldr"]["citations"][0]["link"]


def test_tldr_deterministic_and_special_statuses():
    r = _cited_result()
    assert tldr_data(r) == tldr_data(json.loads(r.model_dump_json()))
    clar = _result(status="needs_clarification", clarification=ClarificationRequest(
        question="Which Acme do you mean?", candidates=[ConfirmedEntity(legal_name="Acme A")]))
    assert tldr(clar).startswith("We need one detail before researching: Which Acme do you mean?")
    assert tldr(_result(status="error", warnings=["key missing"])).startswith("Research failed: key missing.")


def test_sample_fixture_tldr():
    d = tldr_data(EXAMPLES / "sample_result.json")
    assert d["word_count"] <= MAX_WORDS
    assert d["citations"] and all(s["citations"] for s in d["segments"] if s["kind"] == "flag")


def test_score_explainer_without_breakdown():
    x = score_explainer(_cited_result(scores=_scores(FULL, total=37, level="Medium")))
    assert x["available"] is False and "not saved" in x["note"]
    assert x["total"]["score"] == 37 and len(x["areas"]) == 6
    assert x["citations"] == []


def test_score_explainer_with_breakdown_dict_and_raw_key():
    bd = {"total_formula": "weighted average; coverage 80 %", "coverage": 0.8, "range_low": 20, "range_high": 40,
          "confidence_shares": {"high": 0.5, "medium": 0.5, "low": 0.0},
          "areas": [{"area": "legal", "label": "Legal", "score": 60, "level": "High", "weight": 0.13,
                     "coverage_fraction": 1.0, "formula": "mean",
                     "sub_scores": [{"name": "Compliance_Risk_Score", "weight": 0.08, "score": 60, "level": "High",
                                     "confidence": "medium", "contributions": [
                                         {"kind": "event", "ref": "F1", "label": "fine", "points": 50.0,
                                          "rule": "anchor: fresh red event = 50", "source": "S1"},
                                         {"kind": "base", "ref": "events", "label": "base", "points": 12.0,
                                          "rule": "nothing adverse = 12", "source": "S2"}]}]}]}
    r = _cited_result()
    x = score_explainer(r, bd)
    assert x["available"] is True and x["total"]["coverage_pct"] == 80 and x["total"]["range"] == [20, 40]
    sub = x["areas"][0]["sub_scores"][0]
    assert sub["label"] == "Compliance risk" and sub["weight_pct"] == 8
    ev_line, base_line = sub["lines"]
    ids = {c["id"]: c for c in x["citations"]}
    assert ids[ev_line["citations"][0]]["quote"] == QUOTE
    assert ids[base_line["citations"][0]]["source_id"] == "S2"
    raw = json.loads(r.model_dump_json())
    raw["scoring"] = bd
    assert score_explainer(raw)["available"] is True


# ---------------------------------------------------------------------------
# TL;DR = report section 1 (points, order, citations, overrides, wording)
# ---------------------------------------------------------------------------

def _points(d):
    return [s for s in d["segments"] if s["kind"] == "flag"]


def test_fixture_tldr_has_3_to_5_points_in_order_and_matches_section_1():
    from research_agent.report_data import report_sections, section
    d = tldr_data(EXAMPLES / "sample_result.json")
    pts = _points(d)
    assert 3 <= len(pts) <= 5
    rank = {"red": 0, "amber": 1, "green": 2}
    assert [rank[p["colour"]] for p in pts] == sorted(rank[p["colour"]] for p in pts)
    s1 = section(report_sections(EXAMPLES / "sample_result.json"), "summary")
    assert [p["flag_id"] for p in pts] == [x["flag_id"] for x in s1["key_findings"]]
    assert [p["label"] for p in pts] == [x["label"] for x in s1["key_findings"]]
    assert d["score"]["text"] == s1["total"]["text"]
    assert d["score"]["total"] == s1["total"]["score"] and d["score"]["level"] == s1["total"]["level"]
    assert d["score"]["coverage_pct"] == s1["total"]["coverage_pct"]
    assert d["not_assessed"] == s1["not_assessed"]


def test_every_point_has_a_full_citation():
    d = tldr_data(EXAMPLES / "sample_result.json")
    by_id = {c["id"]: c for c in d["citations"]}
    raw = json.loads((EXAMPLES / "sample_result.json").read_text())
    flags = {f["id"]: f for f in raw["flags"]}
    for p in _points(d):
        assert p["citations"], p
        for n in p["citations"]:
            c = by_id[n]
            assert c["quote"] and c["quote"] == " ".join(flags[p["flag_id"]]["quote"].split())
            assert c["source_id"] in flags[p["flag_id"]]["source_ids"]
            assert c["url"].startswith("http") and c["link"].startswith("http")
            assert c["accessed"] and (c["published"] or c["published"] is None)
            assert c["trust_label"].startswith(("✅", "🟨"))
            assert f"[{n}]" in d["text"]


def test_point_selection_red_amber_then_checked():
    from research_agent.models import ResearchResult  # noqa: F401
    areas = ["legal", "operations", "people"]
    reds = [_flag(i, "red", area=areas[i - 1], src=1) for i in range(1, 4)]
    ambers = [_flag(i, "amber", area=areas[i - 4], src=1) for i in range(4, 7)]
    greens = [_flag(i, "green", area="financial", src=1) for i in range(7, 10)]
    d = tldr_data(_result(flags=reds + ambers + greens, sources=[_src(1)]))
    assert [p["colour"] for p in _points(d)] == ["red", "red", "red", "amber", "green"]
    d = tldr_data(_result(flags=[_flag(1, "amber", src=1)] + greens, sources=[_src(1)]))
    assert [p["colour"] for p in _points(d)] == ["amber", "green", "green"]
    assert [p["label"] for p in _points(d)][1] == "Checked, nothing adverse found"
    d = tldr_data(_result(flags=greens, sources=[_src(1)]))
    assert [p["colour"] for p in _points(d)] == ["green"] * 2  # at most 2 points per area
    assert "No red flags or watch items found in the sources checked." in d["text"]


def test_points_cover_areas_not_one_area():
    """Live run Knorr-Bremse 2026-10-18: all five points were green financial items. Now at
    most 2 per area, other areas first, and an older resolved matter shows its area was checked."""
    fin = [_flag(i, "green", area="financial", src=1) for i in range(1, 5)]
    country = _flag(5, "green", area="country", src=1)
    ops = _flag(6, "green", area="operations", src=1)
    old = _flag(7, "neutral", area="legal", src=1, date="2018-07-11")
    old.event_type, old.stale = "antitrust_settlement", True
    pts = _points(tldr_data(_result(flags=fin + [country, ops, old], sources=[_src(1)])))
    by_area = [p["area"] for p in pts]
    assert set(by_area) == {"financial", "country", "operations", "legal"}
    assert all(by_area.count(a) <= 2 for a in by_area)
    assert pts[-1]["flag_id"] == "F7" and pts[-1]["label"] == "Context"
    # Reds from different areas come before a second red from the same area.
    reds = [_flag(1, "red", area="legal", src=1), _flag(2, "red", area="legal", src=1),
            _flag(3, "red", area="legal", src=1), _flag(4, "red", area="people", src=1)]
    pts = _points(tldr_data(_result(flags=reds, sources=[_src(1)])))
    assert sorted(p["flag_id"] for p in pts) == ["F1", "F2", "F4"]  # F3 = third legal point: left out


def test_not_assessed_never_zero_or_low_risk():
    vals = dict(FULL)
    vals["reputation"] = (0, "not_assessed")
    d = tldr_data(_cited_result(scores=_scores(vals, total=30, level="Medium")))
    assert "Not assessed: Reputation & Outside View." in d["text"]
    seg = next(s for s in d["segments"] if s["kind"] == "gaps")["text"]
    assert "0" not in seg and "low risk" not in d["text"].lower() and "no risk" not in d["text"].lower()


def test_overrides_are_reflected():
    r = _cited_result(scores=_scores(FULL, total=75, level="Critical"))
    r.flags[0].knockout = True
    r.verdict = "Knock-out risk found — do not proceed without escalation"
    r.scoring_detail = {"areas": [{"area": "legal", "sub_scores": [], "contributions": [
        {"kind": "override", "ref": "F1", "label": "area floor: 37 raised to 50", "points": 50.0, "rule": "x"}]}],
        "total_contributions": [{"kind": "override", "ref": "F1", "label": "knock-out: total 40 raised to 75",
                                 "points": 75.0, "rule": "x"}]}
    d = tldr_data(r)
    assert "Risk score 75/100 · Critical" in d["text"]
    assert "Legal & Governance raised to 50 (High) by a current red flag from a trusted source." in d["text"]
    assert "Total raised to 75 (Critical) by a knock-out finding from a trusted source." in d["text"]
    assert "Red flag, knock-out:" in d["text"] and d["verdict"]["tone"] == "critical"


def test_tldr_wording_is_plain_and_deterministic():
    d1 = tldr_data(EXAMPLES / "sample_result.json")
    d2 = tldr_data(json.loads((EXAMPLES / "sample_result.json").read_text()))
    assert d1 == d2
    for bad in (".yaml", "appendix", "§", "result.json", "_", "TODO", "fixture", "rule"):
        assert bad not in d1["text"], bad
    assert d1["word_count"] <= MAX_WORDS


def test_intro_from_profile_with_quote_citations():
    from research_agent.app_adapter import build_view
    from research_agent.models import ResearchResult
    from research_agent.report_data import report_sections

    d = tldr_data(EXAMPLES / "sample_result.json")
    assert [p["key"] for p in d["intro"]] == ["description", "headquarters", "founded"]
    assert d["intro"][1]["text"] == "HQ Leipzig, Germany" and d["intro"][2]["text"] == "Founded 1994"
    cites = {c["id"]: c for c in d["citations"]}
    for part in d["intro"]:
        (n,) = part["citations"]
        assert cites[n]["quote"] and cites[n]["trust"] != "unverified"
    assert d["intro"][0]["citations"] == [1]  # first on the card, numbered first
    r = ResearchResult.model_validate_json((EXAMPLES / "sample_result.json").read_text())
    view = build_view(r)
    assert [p["text"] for p in view["tldr"]["intro"]] == [p["text"] for p in d["intro"]]
    vc = {c["n"]: c for c in view["citations"]}
    assert "headquartered in Leipzig" in vc[view["tldr"]["intro"][1]["citations"][0]]["quote"]
    prof = {f["key"]: f for f in next(s for s in report_sections(r) if s["id"] == "profile")["fields"]}
    assert prof["headquarters"]["value"] == "Leipzig, Germany" and prof["headquarters"]["cites"][0]["quote"]
    # No profile -> no intro, nothing guessed.
    r.profile = {}
    assert build_view(r)["tldr"]["intro"] == []


def test_card_points_match_report_key_points():
    from research_agent.app_adapter import build_view
    from research_agent.models import ResearchResult
    from research_agent.report_html import key_points

    r = ResearchResult.model_validate_json((EXAMPLES / "sample_result.json").read_text())
    assert [p["flag_id"] for p in build_view(r)["tldr"]["points"]] == [f.id for f in key_points(r)][:5]
