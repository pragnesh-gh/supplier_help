from datetime import date

import pytest

from research_agent.config import load_rules
from research_agent.models import Flag
from research_agent.rules import (
    area_statuses,
    classify,
    next_steps,
    overall_verdict,
    parse_event_date,
)

TODAY = date(2026, 10, 18)


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def _flag(colour, area="legal", event_type="regulatory_fine", knockout=False, fid="F1", date_="2026-01-01"):
    return Flag(
        id=fid, colour=colour, area=area, event_type=event_type, severity="high", claim_status="confirmed",
        summary="s", quote="q", event_date=date_, source_ids=["S1"], knockout=knockout,
    )


def test_every_event_type_has_a_rule(rules):
    from research_agent.models import EVENT_TYPES
    assert set(rules.event_types) == set(EVENT_TYPES)


def test_recent_fine_is_red(rules):
    c = classify("regulatory_fine", "high", "2025-06-01", "legal", rules, TODAY, default_years=3)
    assert c.colour == "red" and c.area == "legal" and not c.knockout and not c.stale


def test_low_severity_red_becomes_amber(rules):
    c = classify("regulatory_fine", "low", "2025-06-01", "legal", rules, TODAY, default_years=3)
    assert c.colour == "amber"
    assert "low severity" in c.note


def test_old_event_steps_down(rules):
    # product_recall uses default staleness (3 years)
    c = classify("product_recall", "high", "2020-03-01", "operations", rules, TODAY, default_years=3)
    assert c.colour == "neutral" and c.stale
    c2 = classify("safety_accident", "high", "2021-01-01", "people", rules, TODAY, default_years=3)
    assert c2.colour == "amber" and c2.stale


def test_fine_uses_own_staleness_window(rules):
    c = classify("regulatory_fine", "high", "2022-01-01", "legal", rules, TODAY, default_years=3)
    assert c.colour == "red" and not c.stale  # 5-year window


def test_sanctions_never_stale_and_knockout(rules):
    c = classify("sanctions_listing", "high", "2001-01-01", "legal", rules, TODAY, default_years=3)
    assert c.colour == "red" and c.knockout and not c.stale


def test_low_severity_sanctions_is_not_knockout_but_amber(rules):
    c = classify("sanctions_listing", "low", "2026-01-01", "legal", rules, TODAY, default_years=3)
    assert c.colour == "amber" and not c.knockout


def test_unknown_date_is_not_stale(rules):
    c = classify("product_recall", "medium", None, "operations", rules, TODAY, default_years=3)
    assert c.colour == "amber" and not c.stale and "date unknown" in c.note


def test_from_search_area_uses_search_umbrella(rules):
    c = classify("company_disclosed_risk", "medium", "2025", "operations", rules, TODAY, default_years=3)
    assert c.area == "operations" and c.colour == "neutral"


def test_parse_event_date_variants():
    assert parse_event_date("2024-05-06") == date(2024, 5, 6)
    assert parse_event_date("2024-05") == date(2024, 5, 1)
    assert parse_event_date("2024") == date(2024, 1, 1)
    assert parse_event_date("") is None
    assert parse_event_date("last spring") is None


def test_verdict_order(rules):
    assert overall_verdict([], rules).startswith("No red flags found in the sources checked")
    assert overall_verdict([_flag("green")], rules) == rules.verdict.none
    assert overall_verdict([_flag("amber")], rules) == rules.verdict.amber
    assert overall_verdict([_flag("amber"), _flag("red")], rules) == rules.verdict.red
    assert overall_verdict([_flag("red", knockout=True)], rules) == rules.verdict.knockout


def test_verdict_when_nothing_was_checked(rules):
    assert overall_verdict([], rules, pages_read=0) == rules.verdict.no_evidence
    assert overall_verdict([], rules, pages_read=3) == rules.verdict.none


def test_verdict_never_says_no_risk(rules):
    for text in (rules.verdict.none, rules.verdict.amber):
        assert "no risk" not in text.lower()


def test_next_steps_capped_and_ordered(rules):
    flags = [
        _flag("amber", area="operations", fid="F1"),
        _flag("red", area="legal", fid="F2"),
        _flag("red", area="financial", fid="F3", event_type="insolvency_filing", knockout=True),
        _flag("red", area="people", fid="F4"),
    ]
    steps = next_steps(flags, rules)
    assert len(steps) == 3
    assert steps[0] == rules.next_steps["knockout"]
    assert any("legal statement" in s for s in steps)


def test_sort_puts_current_before_stale():
    from research_agent.rules import sort_flags
    old = _flag("amber", fid="OLD", date_="2019")
    old.stale = True
    new = _flag("amber", fid="NEW", date_="2026-02")
    new.severity = "medium"
    assert [f.id for f in sort_flags([old, new])] == ["NEW", "OLD"]


def test_next_steps_default_when_nothing(rules):
    assert next_steps([_flag("green")], rules) == [rules.next_steps["none"]]


def test_area_statuses(rules):
    flags = [_flag("red", area="legal", fid="F1"), _flag("green", area="operations", fid="F2", event_type="iris_certified")]
    pages = {"legal": 2, "operations": 1, "financial": 3}
    labels = {"financial": "Financial", "legal": "Legal & Compliance", "country": "Country & Location",
              "people": "People & Safety", "operations": "Operations & Quality", "reputation": "Reputation"}
    areas = {a.area: a for a in area_statuses(flags, pages, labels)}
    assert len(areas) == 6
    assert areas["legal"].status == "red"
    assert areas["operations"].status == "green"
    assert areas["legal"].trusted_pages_used == 1
    # Financial: 3 pages read but none gave a verified fact -> not assessed, never "No issues found".
    assert areas["financial"].status == "not_assessed"
    assert "3 trusted pages read, none gave usable evidence" in areas["financial"].finding
    assert areas["financial"].trusted_pages_used == 0
    assert areas["country"].status == "not_assessed"
    assert "Not assessed" in areas["country"].finding


def test_neutral_or_stale_facts_never_make_an_area_green(rules):
    labels = {a: a for a in ("financial", "legal", "country", "people", "operations", "reputation")}
    doj = _flag("neutral", area="legal", fid="F7", event_type="antitrust_settlement", date_="2018-04-03")
    doj.stale = True
    st = {a.area: a for a in area_statuses([doj], {"legal": 1}, labels, source_trust={"S1": "trusted"})}
    assert st["legal"].status == "context" and st["legal"].flag_ids == ["F7"]


def test_antitrust_settlement_is_amber_then_context_when_old(rules):
    c = classify("antitrust_settlement", "medium", "2025-01", "legal", rules, TODAY, default_years=3)
    assert c.colour == "amber" and not c.knockout
    old = classify("antitrust_settlement", "medium", "2018-04-03", "legal", rules, TODAY, default_years=3)
    assert old.colour == "neutral" and old.stale


def test_no_issues_found_needs_a_trusted_page_that_gave_a_fact(rules):
    labels = {a: a for a in ("financial", "legal", "country", "people", "operations", "reputation")}
    neutral = _flag("neutral", area="country", fid="F9", event_type="other_neutral")
    areas = {a.area: a for a in area_statuses([neutral], {"country": 1}, labels, source_trust={"S1": "trusted"})}
    assert areas["country"].status == "context" and areas["country"].trusted_pages_used == 1
    neutral.trust = "unverified"
    areas = {a.area: a for a in area_statuses([neutral], {"country": 1}, labels, source_trust={"S1": "unverified"})}
    assert areas["country"].status == "not_assessed" and areas["country"].unverified_pages_used == 1


# --- unverified sources -----------------------------------------------------------


def test_unverified_red_is_capped_to_amber(rules):
    c = classify("regulatory_fine", "high", "2026-01-01", "legal", rules, TODAY, default_years=3, trusted=False)
    assert c.colour == "amber" and c.capped_unverified
    assert "unverified source only: red → amber" in c.note


def test_unverified_sanctions_can_never_knock_out(rules):
    for kind in ("sanctions_listing", "insolvency_filing"):
        c = classify(kind, "high", "2026-09-01", "legal", rules, TODAY, default_years=3, trusted=False)
        assert not c.knockout and c.colour == "amber"


def test_unverified_strength_is_not_shown_as_green(rules):
    c = classify("iris_certified", "low", "2026-01", "operations", rules, TODAY, default_years=3, trusted=False)
    assert c.colour == "neutral" and c.capped_unverified


def test_unverified_amber_stays_amber(rules):
    c = classify("product_recall", "medium", "2026-01", "operations", rules, TODAY, default_years=3, trusted=False)
    assert c.colour == "amber" and not c.capped_unverified


def test_area_with_only_unverified_pages_is_not_assessed():
    labels = {a: a for a in ("financial", "legal", "country", "people", "operations", "reputation")}
    st = {a.area: a for a in area_statuses([], {}, labels, {"reputation": 2})}
    assert st["reputation"].status == "not_assessed" and st["reputation"].unverified_pages_checked == 2


def test_staleness_understands_rfc2822_dates(rules):
    c = classify("regulatory_fine", "high", "Tue, 11 Apr 2017 12:17:32 GMT", "legal", rules, TODAY, default_years=3)
    assert c.stale and c.colour == "amber"


@pytest.mark.parametrize("kind, colour, area, knockout", [
    ("safety_fatality", "red", "people", False), ("environmental_violation", "amber", "people", False),
    ("data_breach", "amber", "operations", False), ("contract_penalty_or_cancellation", "amber", "operations", False),
    ("audit_or_accounting_issue", "red", "financial", False),
    ("supply_chain_forced_labour_listing", "red", "people", True)])
def test_new_event_types(rules, kind, colour, area, knockout):
    c = classify(kind, "high", "2026-06", "legal", rules, TODAY, default_years=3)
    assert (c.colour, c.area, c.knockout) == (colour, area, knockout)
    u = classify(kind, "high", "2026-06", "legal", rules, TODAY, default_years=3, trusted=False)
    assert not u.knockout  # unverified-only can never knock out
