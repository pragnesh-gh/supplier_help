"""Facts-to-scores method (docs/research/facts-to-scores-appendix.md). All data is invented."""

from datetime import date

import pytest

from research_agent.config import load_scoring
from research_agent.models import UMBRELLAS, AreaStatus, Flag, GradingSignals, Source
from research_agent.scoring import (NOT_SCORED, _altman_bucket, _credit_scale, derive, explain_text, level_for,
                                    load_method, round_half_even, score_area, score_detailed, score_result)
from research_agent.scoring_inputs import (AltmanInputs, CountryIndexInput, CreditRatingInput, EcoVadisInput, Evidence,
                                           FineInput, InjuryRateInput, ScoringInputs)

AS_OF = date(2026, 10, 18)
EV = Evidence(source_url="https://example.org/x", quote="q", date="2026-01-01", source_id="S1")
UNV_EV = Evidence(source_url="https://blog.example/x", quote="q", trust="unverified")


def _status(area, trusted=0, unverified=0):
    return AreaStatus(area=area, label=area, status="green" if trusted else "not_assessed", finding="x",
                      pages_checked=trusted + 1, unverified_pages_checked=unverified,
                      trusted_pages_used=trusted, unverified_pages_used=unverified)


def _areas(trusted=(), unverified=()):
    return [_status(a, trusted=1 if a in trusted else 0, unverified=1 if a in unverified else 0) for a in UMBRELLAS]


def _flag(fid="F1", event_type="regulatory_fine", area="legal", severity="high", event_date="2026-10-18",
          trust="trusted", colour="red", sources=("S1",), **signals):
    return Flag(id=fid, colour=colour, area=area, event_type=event_type, severity=severity, claim_status="confirmed",
                summary=f"{event_type} {fid}", quote="q", event_date=event_date, source_ids=list(sources), trust=trust,
                signals=GradingSignals(**signals))


def _eligible(**kw):
    base = dict(publisher_named=True, dated=True, claim_specific_checkable=True, attribution="named_source",
                cites_primary_document=True)
    base.update(kw)
    return base


def _run(flags, areas, inputs=None, sources=None):
    return score_detailed(flags, areas, load_scoring(), inputs=inputs, as_of=AS_OF, sources=sources, default_years=3)


def _sub(rep, name):
    return next(s for a in rep.areas for s in a.sub_scores if s.name == name)


def _area(rep, area):
    return next(a for a in rep.areas if a.area == area)


# --- anchors and derived constants --------------------------------------------------------


def test_constants_are_derived_from_the_anchors():
    d = derive(load_method(scoring=load_scoring()), [("Low", 0), ("Medium", 25), ("High", 50), ("Critical", 75)])
    assert d.p_red == pytest.approx(100 * (1 - 50 / 88)) and d.p_amber == pytest.approx(100 * (1 - 75 / 88))
    assert d.halflife_factor == pytest.approx(0.6462, abs=1e-4)
    assert d.unverified_cap == 25 and d.min_coverage == pytest.approx(0.5) and d.safety_slope == 13


def test_anchor_arithmetic_one_red_50_one_amber_25_nothing_adverse_12():
    rep = _run([_flag()], _areas(trusted={"legal"}))
    assert _sub(rep, "Compliance_Risk_Score").score == 50
    assert _sub(rep, "Governance_Risk_Score").score == 12  # area checked, nothing adverse for this score
    rep = _run([_flag(event_type="major_lawsuit", colour="amber")], _areas(trusted={"legal"}))
    assert _sub(rep, "Compliance_Risk_Score").score == 25
    two = _run([_flag("F1", event_date=None), _flag("F2", event_date=None)], _areas(trusted={"legal"}))
    assert _sub(two, "Compliance_Risk_Score").score == 72  # 71.6: Critical needs 3 reds or a knock-out


def test_low_severity_red_counts_as_amber_and_fine_share_sets_severity():
    rep = _run([_flag(severity="low")], _areas(trusted={"legal"}))
    assert _sub(rep, "Compliance_Risk_Score").score == 25
    small = ScoringInputs(fines=(FineInput(flag_id="F1", amount=1, revenue=10_000, evidence=EV),))  # 0.01 %
    assert _sub(_run([_flag()], _areas(trusted={"legal"}), small), "Compliance_Risk_Score").score == 25
    big = ScoringInputs(fines=(FineInput(flag_id="F1", amount=200, revenue=10_000, evidence=EV),))  # 2 %
    assert _sub(_run([_flag(severity="low")], _areas(trusted={"legal"}), big), "Compliance_Risk_Score").score == 50


def test_round_half_even_matches_dataset_rounding():
    assert [round_half_even(x) for x in (0.5, 1.5, 2.5, 45.5, 71.59)] == [0, 2, 2, 46, 72]


# --- recency ----------------------------------------------------------------------------


def test_red_at_its_stale_date_weighs_like_a_fresh_amber_and_drops_after_twice():
    # safety_accident: red, default staleness 3 years
    at_stale = _run([_flag(event_type="safety_accident", area="people", event_date="2023-10-18")],
                    _areas(trusted={"people"}))
    assert _sub(at_stale, "Safety_Incident_Score").score == 25
    old = _run([_flag(event_type="safety_accident", area="people", event_date="2020-01-01")], _areas(trusted={"people"}))
    assert _sub(old, "Safety_Incident_Score").score == 12


def test_media_uses_two_year_sentiment_decay():
    old = _flag("R1", "leadership_scandal", "reputation", colour="amber", event_date="2024-06-01")
    rep = _run([old], _areas(trusted={"legal", "reputation"}))
    assert _sub(rep, "Governance_Risk_Score").score > 12  # default window: 3 years
    assert _sub(rep, "Media_Sentiment_Score").score == 12  # older than 2 years: dropped
    fresh = _run([_flag("R1", "leadership_scandal", "reputation", colour="amber")], _areas(trusted={"reputation"}))
    assert _sub(fresh, "Media_Sentiment_Score").score == 25 and _sub(fresh, "Market_Sentiment_Score").score == 25


def test_each_event_feeds_only_the_scores_its_definition_names():
    rep = _run([_flag()], _areas(trusted={"legal", "reputation"}))
    assert _sub(rep, "Compliance_Risk_Score").score == 50
    assert _sub(rep, "Media_Sentiment_Score").score == 12  # a fine is not counted again in Media
    assert _sub(rep, "Market_Sentiment_Score").score == 12


def test_sanctions_never_decay():
    rep = _run([_flag(event_type="sanctions_listing", event_date="2010-01-01")], _areas(trusted={"legal"}))
    assert _sub(rep, "Compliance_Risk_Score").score == 100


# --- unverified sources -------------------------------------------------------------------


def test_hearsay_scores_zero_and_alone_never_assesses_an_area():
    hearsay = _flag(trust="unverified", **_eligible(attribution="anonymous_or_rumour"))
    rep = _run([hearsay], _areas(unverified={"legal"}))
    assert _sub(rep, "Compliance_Risk_Score").score is None
    assert _area(rep, "legal").score is None
    with_trusted_page = _run([hearsay], _areas(trusted={"legal"}))
    comp = _sub(with_trusted_page, "Compliance_Risk_Score")
    assert comp.score == 12
    assert any(c.points == 0 and "E1 not on the record" in c.rule for c in comp.contributions)


def test_eligible_unverified_weights_follow_admiralty_grades():
    inputs = ScoringInputs(source_reliability={"U1": "C"})
    c2 = _run([_flag(trust="unverified", sources=("U1",), **_eligible())], _areas(trusted={"legal"}), inputs)
    assert _sub(c2, "Compliance_Risk_Score").score == round_half_even(100 - 88 * (1 - 0.4318 * 0.55))  # 33
    c3 = _run([_flag(trust="unverified", sources=("U1",), **_eligible(cites_primary_document=False))],
              _areas(trusted={"legal"}), inputs)
    assert _sub(c3, "Compliance_Risk_Score").score == round_half_even(100 - 88 * (1 - 0.4318 * 0.40))  # 27
    d_no_doc = _run([_flag(trust="unverified", sources=("U9",), **_eligible(cites_primary_document=False))],
                    _areas(trusted={"legal"}))
    assert _sub(d_no_doc, "Compliance_Risk_Score").score == 12  # reliability D needs a primary document


def test_official_domain_is_reliability_b_and_trusted_confirmation_is_full_weight():
    src = Source(id="U1", url="https://www.justice.gov/x", title="t", publisher="DOJ", tier="open_web",
                 trust="unverified", retrieved_at="2026-10-18", found_by="legal-ow")
    rep = _run([_flag(trust="unverified", sources=("U1",), **_eligible())], _areas(trusted={"legal"}), sources=[src])
    assert _sub(rep, "Compliance_Risk_Score").score == 33
    confirmed = _run([_flag(trust="unverified", corroborated_by_trusted=True)], _areas(trusted={"legal"}))
    assert _sub(confirmed, "Compliance_Risk_Score").score == 50


def test_unverified_events_add_at_most_one_band():
    inputs = ScoringInputs(source_reliability={"U1": "C"})
    many = [_flag(f"U{i}", event_date=f"2026-0{i}-01", trust="unverified", sources=("U1",), **_eligible())
            for i in range(1, 9)]
    rep = _run(many, _areas(trusted={"legal"}), inputs)
    comp = _sub(rep, "Compliance_Risk_Score")
    assert comp.score == 12 + 25 and comp.includes_unverified and comp.confidence == "low"
    assert any(c.kind == "cap" for c in comp.contributions)


def test_unverified_knockout_is_never_a_knockout():
    inputs = ScoringInputs(source_reliability={"U1": "C"})
    rep = _run([_flag(event_type="sanctions_listing", trust="unverified", sources=("U1",), **_eligible())],
               _areas(trusted={"legal"}), inputs)
    comp = _sub(rep, "Compliance_Risk_Score")
    assert comp.score == 12 and not rep.knockout
    assert any("unconfirmed knock-out lead" in c.rule for c in comp.contributions)
    trusted = _run([_flag(event_type="sanctions_listing")], _areas(trusted={"legal"}))
    assert _sub(trusted, "Compliance_Risk_Score").score == 100 and trusted.knockout


# --- dedupe, not assessed, coverage --------------------------------------------------------


def test_same_event_in_two_flags_counts_once():
    rep = _run([_flag("F1", event_date="2026-10-03"), _flag("F2", event_date="2026-10-18", trust="unverified",
                                                           **_eligible())], _areas(trusted={"legal"}))
    comp = _sub(rep, "Compliance_Risk_Score")
    single = _sub(_run([_flag("F1", event_date="2026-10-03")], _areas(trusted={"legal"})), "Compliance_Risk_Score")
    assert comp.score == single.score == 50
    assert any(c.kind == "not_counted" and c.ref == "F2" and "same event as F1" in c.rule for c in comp.contributions)


def test_not_assessed_is_none_never_zero():
    rep = _run([], _areas())
    assert rep.total is None and all(a.score is None for a in rep.areas)
    assert all(s.score is None for a in rep.areas for s in a.sub_scores)
    rep = _run([_flag()], _areas(trusted={"legal"}))
    assert _sub(rep, "Political_Stability_Score").score is None  # index score without an input
    assert _sub(rep, "Industry_Benchmark_Score").score is None and _sub(rep, "External_Intelligence_Score").score is None
    card = score_result([_flag()], _areas(trusted={"legal"}), load_scoring(), as_of=AS_OF)
    fin = next(a for a in card.areas if a.area == "financial")
    assert fin.score is None and fin.coverage == "not_assessed"


def test_total_needs_half_the_weight_and_shows_the_range():
    rep = _run([_flag()], _areas(trusted={"legal"}))
    assert rep.total is None and not rep.total_shown and "below the 50 % minimum" in rep.total_formula
    assert rep.range_low is not None and rep.range_high is not None and rep.range_low < rep.range_high


def test_score_result_without_config_keeps_placeholders():
    card = score_result([_flag()], _areas(trusted={"legal"}))
    assert card.total is None and card.total_method == NOT_SCORED and all(a.score is None for a in card.areas)


def test_score_area_public_function():
    s = score_area("legal", [_flag()], "assessed", ["Compliance_Risk_Score", "Governance_Risk_Score"], as_of=AS_OF)
    assert s.sub_scores == {"Compliance_Risk_Score": 50, "Governance_Risk_Score": 12}
    # weighted mean 35 (Medium), lifted to 50 (High) by the trusted-red area floor
    assert round_half_even((50 * 0.08 + 12 * 0.05) / 0.13) == 35 and s.score == 50 and s.level == "High"
    assert score_area("legal", [], "not_assessed", ["Compliance_Risk_Score"], as_of=AS_OF).score is None


# --- index scores -----------------------------------------------------------------------------


def test_credit_scale_and_crr_rule():
    m = load_method()
    scale = _credit_scale(m.credit)
    assert round_half_even(scale["BBB"]) == 21 and round_half_even(scale["BBB-"]) == 33
    assert scale["AAA"] == 0 and scale["D"] == 100 and round_half_even(scale["CCC/C"]) == 87
    vals = [scale[k] for k in m.credit.pd3_percent]
    assert vals == sorted(vals)  # monotone
    ins = ScoringInputs(credit_ratings=(CreditRatingInput(agency="S&P", rating="A-", evidence=EV),
                                        CreditRatingInput(agency="Moody's", rating="Baa3", evidence=EV),
                                        CreditRatingInput(agency="Fitch", rating="BBB", evidence=EV)))
    rep = _run([], _areas(trusted={"financial"}), ins)
    assert _sub(rep, "Credit_Rating_Score").score == 21  # worse of the two best (A-, BBB)
    assert _sub(_run([], _areas(), ins), "Credit_Rating_Score").score is None  # pipeline says not assessed


def test_altman_nearest_median_and_insolvency_knockout():
    m = load_method()
    assert _altman_bucket(5.70, m.altman) == "BBB-" and _altman_bucket(5.725, m.altman) == "BBB-"  # tie -> worse
    rep = _run([_flag(event_type="insolvency_filing", area="financial")], _areas(trusted={"financial"}))
    assert _sub(rep, "Financial_Health_Score").score == 100 and _sub(rep, "Credit_Rating_Score").score == 100


def test_safety_rate_ratio_and_unverified_inputs_not_used():
    ir = InjuryRateInput(metric="TRIR", company_rate=4.8, benchmark_rate=2.4, benchmark_label="BLS 2024 NAICS 3365",
                         year=2025, evidence=EV, benchmark_evidence=EV)
    rep = _run([], _areas(trusted={"people"}), ScoringInputs(injury_rate=ir))
    assert _sub(rep, "Safety_Incident_Score").score == 25  # twice the industry rate = one amber
    bad = ScoringInputs(ecovadis=EcoVadisInput(score=80, evidence=UNV_EV))
    esg = _sub(_run([], _areas(trusted={"people"}), bad), "ESG_Performance_Score")
    assert esg.score == 12 and any(c.kind == "input_not_used" for c in esg.contributions)


def test_country_scores_use_sites_then_hq():
    rows = (CountryIndexInput(index="wgi_political_stability", country_code="DE", value=70, year=2024, basis="hq",
                              evidence=EV),
            CountryIndexInput(index="wgi_political_stability", country_code="PL", value=60, year=2024, basis="site",
                              share=1, evidence=EV),
            CountryIndexInput(index="wgi_political_stability", country_code="CZ", value=80, year=2024, basis="site",
                              share=3, evidence=EV))
    rep = _run([], _areas(trusted={"country"}), ScoringInputs(country_indices=rows))
    assert _sub(rep, "Political_Stability_Score").score == round_half_even((40 * 1 + 20 * 3) / 4)  # 25
    assert _area(rep, "country").score is not None


# --- determinism, breakdown, sanity pair --------------------------------------------------------


def _troubled():
    ins = ScoringInputs(
        credit_ratings=(CreditRatingInput(agency="S&P", rating="B-", outlook="negative", evidence=EV),),
        altman=AltmanInputs(fiscal_year_end="2025-12-31", current_assets=90, current_liabilities=120,
                            retained_earnings=-40, ebit=-5, book_equity=20, total_liabilities=180, total_assets=200,
                            evidence=EV),
        fines=(FineInput(flag_id="L1", amount=300, revenue=10_000, evidence=EV),),
        country_indices=(CountryIndexInput(index="wgi_political_stability", country_code="ES", value=62, year=2024,
                                           basis="hq", evidence=EV),
                         CountryIndexInput(index="inform_human_hazard", country_code="ES", value=1.8, year=2025,
                                           basis="hq", evidence=EV),
                         CountryIndexInput(index="inform_natural_hazard", country_code="ES", value=3.0, year=2025,
                                           basis="hq", evidence=EV)))
    flags = [_flag("P1", "profit_warning", "financial", colour="amber", event_date="2026-07-01"),
             _flag("L1", "regulatory_fine", "legal", event_date="2026-05-01"),
             _flag("L2", "fraud_or_corruption_case", "legal", event_date="2026-02-01"),
             _flag("O1", "delivery_failure", "operations", colour="amber", event_date="2026-09-01"),
             _flag("O2", "delivery_failure", "operations", colour="amber", event_date="2026-03-01"),
             _flag("O3", "product_recall", "operations", colour="amber", event_date="2026-06-01"),
             _flag("R1", "leadership_scandal", "reputation", colour="amber", event_date="2026-08-01")]
    return flags, ins


def _stable():
    ins = ScoringInputs(
        credit_ratings=(CreditRatingInput(agency="S&P", rating="A-", outlook="stable", evidence=EV),
                        CreditRatingInput(agency="Moody's", rating="A3", evidence=EV)),
        altman=AltmanInputs(fiscal_year_end="2025-12-31", current_assets=160, current_liabilities=70,
                            retained_earnings=90, ebit=24, book_equity=110, total_liabilities=90, total_assets=200,
                            evidence=EV),
        injury_rate=InjuryRateInput(metric="TRIR", company_rate=1.9, benchmark_rate=2.4, benchmark_label="BLS 3365",
                                    year=2025, evidence=EV, benchmark_evidence=EV),
        ecovadis=EcoVadisInput(score=72, evidence=EV),
        country_indices=(CountryIndexInput(index="wgi_political_stability", country_code="DE", value=72, year=2024,
                                           basis="hq", evidence=EV),
                         CountryIndexInput(index="inform_human_hazard", country_code="DE", value=1.2, year=2025,
                                           basis="hq", evidence=EV),
                         CountryIndexInput(index="inform_natural_hazard", country_code="DE", value=2.0, year=2025,
                                           basis="hq", evidence=EV)))
    flags = [_flag("G1", "iso_certified", "operations", colour="green", severity="low"),
             _flag("G2", "award_or_major_contract", "reputation", colour="green", severity="low"),
             _flag("S1", "strike_or_labour_dispute", "people", colour="amber", severity="low", event_date="2024-11-01"),
             _flag("N1", "other_neutral", "legal", colour="neutral", severity="low")]
    return flags, ins


def test_sanity_pair_troubled_high_stable_low():
    all_areas = _areas(trusted=set(UMBRELLAS))
    t_flags, t_in = _troubled()
    trouble = _run(t_flags, all_areas, t_in)
    assert level_for(_area(trouble, "financial").score) in ("High", "Critical")
    assert level_for(_area(trouble, "legal").score) in ("High", "Critical")
    s_flags, s_in = _stable()
    stable = _run(s_flags, all_areas, s_in)
    assert all(a.level in ("Low", "Medium") for a in stable.areas if a.score is not None)
    assert stable.total_level in ("Low", "Medium") and stable.total_shown
    assert trouble.total is not None and stable.total is not None
    for area in ("financial", "legal"):
        assert (_area(trouble, area).score or 0) - (_area(stable, area).score or 0) >= 25


def test_same_input_same_output_byte_for_byte():
    flags, ins = _troubled()
    a = _run(flags, _areas(trusted=set(UMBRELLAS)), ins)
    b = _run(list(reversed(flags)), _areas(trusted=set(UMBRELLAS)), ins)
    assert a.model_dump_json() == b.model_dump_json()
    assert explain_text(a) == explain_text(b)
    text = explain_text(a)
    assert "How was this scored?" in text and "L1" in text and "anchor: fresh red = 50" in text


def test_method_config_matches_scoring_yaml():
    cfg = load_scoring()
    m = load_method(scoring=cfg)
    cols = [c for a in cfg.areas.values() for c in a.sub_scores]
    assert len(cols) == len(set(cols)) == 18 == len(m.sub_scores)
    assert sum(s.weight for s in m.sub_scores.values()) == pytest.approx(1.0)
    assert m.licensed.msci is False and m.country_basis == "sites_then_hq"  # Decision 2 and 3 defaults


def test_old_doj_antitrust_settlement_is_a_small_decayed_compliance_contribution():
    f = _flag("A1", "antitrust_settlement", "legal", colour="neutral", severity="medium", event_date="2018-07-11")
    rep = _run([f], _areas(trusted={"legal", "reputation"}))
    comp = _sub(rep, "Compliance_Risk_Score")
    ev = next(c for c in comp.contributions if c.ref == "A1")
    assert ev.kind == "event" and 0 < (ev.points or 0) < 5  # amber 14.77 x 0.5^(8.27/3.23) = 2.5
    assert comp.score == 14 and not rep.knockout
    assert _sub(rep, "Media_Sentiment_Score").score == 12  # not a reputation event: Media not fed


# --- pipeline status wins, and country figures from Flag.data ---------------------------------

def _sample_like():
    """The regenerated sample: reputation has no trusted evidence, adverse events elsewhere."""
    flags = [_flag("F5", "regulatory_fine", "legal", event_date="2026-03-11"),
             _flag("F9", "product_recall", "operations", colour="amber", event_date="2026-08"),
             _flag("F8", "profit_warning", "financial", colour="amber", event_date="2026-07-13"),
             _flag("F12", "major_lawsuit", "legal", colour="amber", event_date="2026-05-18"),
             _flag("F6", "strike_or_labour_dispute", "people", colour="amber", event_date="2026-02"),
             _flag("F10", "fraud_or_corruption_case", "legal", colour="amber", trust="unverified", event_date="2026-04"),
             _flag("F7", "safety_accident", "people", colour="amber", event_date="2019")]
    areas = [_status(a, trusted=2) for a in ("financial", "legal", "country", "operations")]
    areas += [_status("people", trusted=1), _status("reputation")]
    return flags, areas


def test_pipeline_not_assessed_area_is_never_scored():
    flags, areas = _sample_like()
    rep = _run(flags, areas)
    rep_area = _area(rep, "reputation")
    assert rep_area.score is None and all(s.score is None for s in rep_area.sub_scores)
    card = score_result(flags, areas, load_scoring(), as_of=AS_OF)
    r = next(a for a in card.areas if a.area == "reputation")
    assert r.score is None and r.coverage == "not_assessed"


def test_context_only_area_scores_only_data_values():
    ctx = AreaStatus(area="legal", label="legal", status="context", finding="x", pages_checked=1,
                     trusted_pages_used=1)
    areas = [ctx if a == "legal" else _status(a) for a in UMBRELLAS]
    rep = _run([_flag("A1", "antitrust_settlement", "legal", colour="neutral", event_date="2018-07-11")], areas)
    assert _area(rep, "legal").score is None


def test_wgi_figures_on_a_data_flag_score_political_stability():
    url = "https://api.worldbank.org/v2/country/DE/indicator/GOV_WGI_PV.SC;GOV_WGI_CC.SC?format=json&source=3&mrv=1"
    data = {"figures": [{"indicator": "GOV_WGI_PV.SC", "value": 69.2575511, "year": 2025, "source_url": url},
                        {"indicator": "GOV_WGI_CC.SC", "value": 81.85, "year": 2025, "source_url": url},
                        {"indicator": "CPI", "value": 77.0, "year": 2025,
                         "source_url": "https://www.transparency.org/en/cpi/2025"}]}
    f = _flag("F1", "country_risk_low", "country", colour="green", event_date="2025")
    f.data = data
    rep = _run([f], _areas(trusted={"country"}))
    ps = _sub(rep, "Political_Stability_Score")
    assert ps.score == round_half_even(100 - 69.2575511) == 31 and ps.confidence == "high"
    assert "DE 69.2576 (2025)" in ps.contributions[0].label
    assert _sub(rep, "Geopolitical_Risk_Score").score is None and _sub(rep, "Environmental_Exposure_Score").score is None
    unv = _flag("F1", "country_risk_low", "country", colour="green", trust="unverified", event_date="2025")
    unv.data = data
    assert _sub(_run([unv], _areas(trusted={"country"})), "Political_Stability_Score").score is None


# --- override rules (appendix §A5) -----------------------------------------------------------


def test_trusted_current_red_flag_lifts_its_area_to_high():
    rep = _run([_flag()], _areas(trusted={"legal"}))
    legal = _area(rep, "legal")
    assert legal.score == 50 and legal.level == "High"  # weighted mean of 50 and 12 is 35
    ov = [c for c in legal.contributions if c.kind == "override"]
    assert len(ov) == 1 and ov[0].ref == "F1" and ov[0].points == 50
    assert "S&P Global Ratings" in ov[0].rule and "overriding factors" in ov[0].rule
    assert "area floor" in legal.formula and "override" in explain_text(rep)
    card = score_result([_flag()], _areas(trusted={"legal"}), load_scoring(), as_of=AS_OF)
    assert next(a for a in card.areas if a.area == "legal").score == 50


def test_area_floor_not_applied_for_unverified_or_old_red_flags():
    inputs = ScoringInputs(source_reliability={"U1": "C"})
    unv = _run([_flag(trust="unverified", sources=("U1",), **_eligible())], _areas(trusted={"legal"}), inputs)
    assert _area(unv, "legal").score is not None and _area(unv, "legal").score < 50
    assert not _area(unv, "legal").contributions
    old = _run([_flag(event_date="2020-01-01")], _areas(trusted={"legal"}))  # fine stale after 5 years
    assert (_area(old, "legal").score or 0) < 50 and not _area(old, "legal").contributions


def test_trusted_knockout_lifts_total_to_critical():
    rep = _run([_flag(event_type="sanctions_listing")], _areas(trusted=set(UMBRELLAS)))
    assert rep.knockout and rep.total_shown
    weighted = round_half_even(sum(s.weight * (s.score or 0) for a in rep.areas for s in a.sub_scores) / rep.coverage)
    assert weighted < 75 and rep.total == 75 and rep.total_level == "Critical" and rep.card.total == 75
    ov = rep.total_contributions
    assert len(ov) == 1 and ov[0].kind == "override" and ov[0].points == 75 and "S&P Global Ratings" in ov[0].rule
    assert f"max({weighted}, 75)" in rep.total_formula


def test_unverified_knockout_never_lifts_the_total():
    inputs = ScoringInputs(source_reliability={"U1": "C"})
    rep = _run([_flag(event_type="sanctions_listing", trust="unverified", sources=("U1",), **_eligible())],
               _areas(trusted=set(UMBRELLAS)), inputs)
    assert not rep.knockout and not rep.total_contributions and (rep.total or 0) < 75


def test_no_override_leaves_the_weighted_average():
    rep = _run([_flag(event_type="major_lawsuit", colour="amber")], _areas(trusted=set(UMBRELLAS)))
    weighted = sum(s.weight * (s.score or 0) for a in rep.areas for s in a.sub_scores)
    assert rep.total == round_half_even(weighted / rep.coverage) and not rep.total_contributions
    assert all(not a.contributions for a in rep.areas)
    assert all(a.score == round_half_even(sum(s.weight * s.score for s in a.sub_scores if s.score is not None)
                                          / sum(s.weight for s in a.sub_scores if s.score is not None))
               for a in rep.areas if a.score is not None)


def test_override_numbers_come_from_config():
    m = load_method(scoring=load_scoring())
    assert m.overrides.trusted_red_area_floor == 50 and m.overrides.knockout_total_floor == 75
    low = m.model_copy(update={"overrides": m.overrides.model_copy(update={"trusted_red_area_floor": 40})})
    rep = score_detailed([_flag()], _areas(trusted={"legal"}), load_scoring(), as_of=AS_OF, method=low,
                         default_years=3)
    assert _area(rep, "legal").score == 40
