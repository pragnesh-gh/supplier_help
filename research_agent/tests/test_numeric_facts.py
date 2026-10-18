"""Numbers for scoring: quote-checked, value inside the quote, page about the company, parsed."""

import json

import pytest

from research_agent.config import load_all
from research_agent.fakes import FakeLLM, FakeSearch, load_fixture
from research_agent.models import Flag, NumberOut, Source
from research_agent.numeric_facts import (
    accept_pages,
    build_inputs,
    check_number,
    parse_number,
    source_reliability,
    value_in_quote,
)
from research_agent.orchestrator import run_research
from research_agent.scoring_inputs import ScoringInputs

PAGE = ("Konzernbilanz zum 31.12.2025 in Mio. EUR: Bilanzsumme 9.523,4. Umsatz 7.887 Mio. EUR. "
        "S&P bestätigte das Rating A mit stabilem Ausblick. Moody's rates the company A3.")


def _src(trust="trusted", tier="company_own", sid="S1"):
    return Source(id=sid, url="https://kb.example/ar", title="AR", publisher="KB", tier=tier, trust=trust,
                  retrieved_at="2026-10-18", found_by="financial-1")


def _n(kind, value, quote, unit="Mio. EUR", period="2025-12-31", detail="", outlook=""):
    return NumberOut(kind=kind, value=value, unit=unit, period=period, detail=detail, outlook=outlook, quote=quote)


@pytest.mark.parametrize("raw, german, out", [("9,523.4", False, 9523.4), ("9.523,4", False, 9523.4),
                                              ("4,2", False, 4.2), ("7,887", False, 7887), ("7.887", True, 7887),
                                              ("7.887", False, 7.887), ("(12.5)", False, -12.5), ("A-", False, None)])
def test_parse_number(raw, german, out):
    assert parse_number(raw, german) == out


def test_value_must_be_whole_and_inside_quote():
    assert value_in_quote("9.523,4", "Bilanzsumme 9.523,4.")
    assert not value_in_quote("9.523", "Bilanzsumme 9.523,4")
    assert value_in_quote("A3", "Moody's rates the company A3.") and not value_in_quote("A", "rated A3")


def test_german_accounts_line_parsed_with_scale_and_currency():
    f = check_number(_n("total_assets", "9.523,4", "Bilanzsumme 9.523,4"), PAGE, _src())
    assert f.accepted and f.amount == pytest.approx(9_523_400_000) and f.currency == "EUR" and f.company_stated
    g = check_number(_n("revenue", "7.887", "Umsatz 7.887 Mio. EUR"), PAGE, _src())
    assert g.amount == pytest.approx(7_887_000_000)


@pytest.mark.parametrize("n, reason", [
    (_n("total_assets", "9.999,0", "Bilanzsumme 9.999,0"), "quote not found in source text"),
    (_n("total_assets", "1.000,0", "Bilanzsumme 9.523,4"), "value not in the quote"),
    (_n("credit_rating", "A", "S&P bestätigte das Rating A mit stabilem Ausblick", detail="Fitch"),
     "rating agency not named in the quote"),
    (_n("total_assets", "9.523,4", "Bilanzsumme 9.523,4", unit=""), "currency not stated"),
])
def test_rejections(n, reason):
    f = check_number(n, PAGE, _src())
    assert not f.accepted and f.reject_reason == reason


def test_rating_with_agency_in_quote():
    f = check_number(_n("credit_rating", "A3", "Moody's rates the company A3", unit="", detail="Moody's"), PAGE, _src())
    assert f.accepted and f.detail == "Moody's" and f.amount is None


def test_numbers_only_from_pages_about_the_company():
    a = check_number(_n("total_assets", "9.523,4", "Bilanzsumme 9.523,4"), PAGE, _src(sid="S1"))
    b = check_number(_n("total_assets", "9.523,4", "Bilanzsumme 9.523,4"), PAGE, _src(sid="S2"))
    flag = Flag(id="F1", colour="green", area="financial", event_type="credit_upgrade_or_strong_results",
                severity="low", claim_status="confirmed", summary="s", quote="q", source_ids=["S1"])
    accept_pages([a, b], [flag])
    assert a.accepted and not b.accepted and b.reject_reason == "page gave no verified fact about this company"


def test_source_reliability_grades():
    s1, s2 = _src("unverified", "open_web", "S1"), _src("unverified", "open_web", "S2")
    grades = source_reliability([s1, s2], {"S1": "Our corrections policy ... Editor-in-chief: A. B.", "S2": "blog"})
    assert grades == {"S1": "C", "S2": "D"}


def test_pipeline_fills_scoring_inputs():
    fx = load_fixture()
    r = run_research("Veltrava", "DE", "veltrava-rail.example", llm=FakeLLM(fx), search=FakeSearch(fx), config=load_all())
    si = ScoringInputs.model_validate(r.scoring_inputs)
    assert [(c.agency, c.rating, c.outlook) for c in si.credit_ratings] == [("S&P", "BB+", "stable")]
    assert si.altman is not None and si.altman.total_assets == pytest.approx(402_500_000)
    assert si.altman.total_liabilities == pytest.approx(402_500_000 - 158_900_000)  # derived: assets - equity
    fine = si.fines[0]
    assert fine.amount == pytest.approx(4_200_000) and fine.revenue == pytest.approx(412_000_000)
    assert next(f for f in r.flags if f.id == fine.flag_id).event_type == "regulatory_fine"
    assert si.injury_rate is not None and si.injury_rate.company_rate == 1.9 and si.injury_rate.benchmark_rate == 2.4
    assert si.ecovadis is not None and si.ecovadis.score == 68
    ci = si.country_indices[0]
    assert ci.index == "wgi_political_stability" and ci.basis == "hq" and ci.country_code == "DE"
    assert ci.evidence.quote == '"date":"2025","value":69.2575511'  # exact text of the World Bank response
    # Every accepted number's value appears in its quote; the planted wrong number was rejected.
    assert all(n.value in n.quote for n in r.numeric_facts if n.accepted)
    assert any(n.value == "999" and n.reject_reason == "value not in the quote" for n in r.numeric_facts)
    assert si.source_reliability == {s.id: "D" for s in r.sources if s.trust == "unverified"}
    assert r.scoring_detail is not None and r.scoring_detail["as_of"] and r.scores.total is not None
