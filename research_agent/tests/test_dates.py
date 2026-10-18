"""Dates from Tavily (ISO or RFC 2822) and models are normalized once, to ISO."""

from datetime import date

import pytest

from research_agent.dates import month_key, normalize_date, parse_date
from research_agent.rules import parse_event_date


@pytest.mark.parametrize("raw, iso", [
    ("Wed, 29 Jul 2026 00:00:00 GMT", "2026-07-29"),
    ("Thu, 07 May 2026 05:00:51 GMT", "2026-05-07"),
    ("2026-07-29T05:00:51Z", "2026-07-29"),
    ("2026-07-29 05:00:51+02:00", "2026-07-29"),
    ("2026-07-29", "2026-07-29"),
    ("2026-7", "2026-07"),
    ("2026", "2026"),
    (" 2025-09 ", "2025-09"),
])
def test_normalize_date(raw, iso):
    assert normalize_date(raw) == iso


@pytest.mark.parametrize("raw", [None, "", "yesterday", "Wed, 29 Ju", "2026-13-01", "0001-01-01"])
def test_unparseable_dates_are_none(raw):
    assert normalize_date(raw) is None


def test_parse_and_month_key():
    assert parse_date("Tue, 11 Apr 2023 12:17:32 GMT") == date(2023, 4, 11)
    assert parse_event_date("2025-09") == date(2025, 9, 1)
    assert month_key("Wed, 29 Jul 2026 00:00:00 GMT") == month_key("2026-07-03") == "2026-07"
    assert month_key("2026") == "2026"
