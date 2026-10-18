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
