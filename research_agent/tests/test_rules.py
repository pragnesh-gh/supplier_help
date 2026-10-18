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
    assert areas["financial"].status == "green"  # checked, nothing found
    assert "No issues found" in areas["financial"].finding
    assert areas["country"].status == "not_assessed"
    assert "Not assessed" in areas["country"].finding
