"""Deterministic flag rules. The language model never picks a colour; this module does.

All behaviour is driven by ``config/rules.yaml`` so non-coders can read and change it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

from .config import Rules
from .models import UMBRELLAS, AreaStatus, Colour, Flag, Severity, UmbrellaId

_STEP_DOWN: dict[Colour, Colour] = {"red": "amber", "amber": "neutral", "green": "neutral", "neutral": "neutral"}
COLOUR_RANK: dict[str, int] = {"red": 0, "amber": 1, "green": 2, "neutral": 3}


@dataclass(frozen=True)
class Classification:
    colour: Colour
    area: UmbrellaId
    knockout: bool
    stale: bool
    note: str


def parse_event_date(value: str | None) -> date | None:
    """Parse 'YYYY-MM-DD', 'YYYY-MM' or 'YYYY'. Anything else -> None."""
    if not value:
        return None
    m = re.fullmatch(r"\s*(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?\s*", value)
    if not m:
        m2 = re.match(r"\s*(\d{4})-(\d{2})-(\d{2})", value)  # tolerate ISO timestamps
        if not m2:
            return None
        m = m2
    year = int(m.group(1))
    month = int(m.group(2) or 1)
    day = int(m.group(3) or 1)
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _years_between(earlier: date, later: date) -> float:
    return (later - earlier).days / 365.25


def classify(
    event_type: str,
    severity: Severity,
    event_date: str | None,
    search_area: UmbrellaId,
    rules: Rules,
    today: date,
    default_years: int,
) -> Classification:
    rule = rules.event_types[event_type]
    colour: Colour = rule.colour
    notes: list[str] = [f"{event_type} → {colour}"]
    area: UmbrellaId = search_area if rule.area == "from_search" else cast(UmbrellaId, rule.area)

    if severity == "low" and colour == "red":
        colour = "amber"
        notes.append("low severity → amber")

    stale = False
    when = parse_event_date(event_date)
    window = rule.stale_after_years
    if when is None:
        notes.append("date unknown, treated as current")
    elif window != "never":
        years = default_years if window is None else window
        if _years_between(when, today) > years:
            stale = True
            new = _STEP_DOWN[colour]
            notes.append(f"older than {years} years: {colour} → {new}")
            colour = new

    knockout = bool(rule.knockout and colour == "red")
    if knockout:
        notes.append("knock-out rule")
    return Classification(colour=colour, area=area, knockout=knockout, stale=stale, note="; ".join(notes))


def overall_verdict(flags: list[Flag], rules: Rules, pages_read: int | None = None) -> str:
    """Text verdict from flags. ``pages_read=0`` means nothing was checked at all."""
    if pages_read == 0 and not flags:
        return rules.verdict.no_evidence
    if any(f.knockout for f in flags):
        return rules.verdict.knockout
    if any(f.colour == "red" for f in flags):
        return rules.verdict.red
    if any(f.colour == "amber" for f in flags):
        return rules.verdict.amber
    return rules.verdict.none


def sort_flags(flags: list[Flag]) -> list[Flag]:
    """Most serious first: knock-out, colour, current before stale, severity, then most recent."""
    sev = {"high": 0, "medium": 1, "low": 2}

    def key(f: Flag) -> tuple[int, int, int, int, int]:
        d = parse_event_date(f.event_date)
        return (0 if f.knockout else 1, COLOUR_RANK[f.colour], int(f.stale), sev[f.severity], -(d.toordinal() if d else 0))

    return sorted(flags, key=key)


def next_steps(flags: list[Flag], rules: Rules, limit: int = 3) -> list[str]:
    steps: list[str] = []
    table = rules.next_steps
    if any(f.knockout for f in flags):
        steps.append(str(table["knockout"]))
    for f in sort_flags([f for f in flags if f.colour in ("red", "amber")]):
        area_steps = table.get(f.area)
        if isinstance(area_steps, Mapping):
            text = area_steps.get(f.colour)
            if text and str(text) not in steps:
                steps.append(str(text))
    if not steps:
        steps.append(str(table["none"]))
    return steps[:limit]


def area_statuses(
    flags: list[Flag], pages_checked: Mapping[str, int], labels: Mapping[str, str]
) -> list[AreaStatus]:
    out: list[AreaStatus] = []
    for area in UMBRELLAS:
        own = sort_flags([f for f in flags if f.area == area and f.colour != "neutral"])
        pages = pages_checked.get(area, 0)
        status: Literal["red", "amber", "green", "not_assessed"]
        neutral = [f for f in flags if f.area == area and f.colour == "neutral"]
        if own:
            top = own[0]
            status = "green" if top.colour == "neutral" else top.colour
            finding = top.summary
        elif neutral:
            # Checked; only neutral context found (e.g. country data, company-disclosed risk).
            own = neutral[:1]
            status = "green"
            finding = neutral[0].summary
        elif pages > 0:
            status = "green"
            finding = "No issues found in the sources checked."
        else:
            status = "not_assessed"
            finding = "Not assessed — no trusted source returned evidence."
        out.append(
            AreaStatus(
                area=area,
                label=labels.get(area, area),
                status=status,
                finding=finding,
                flag_ids=[f.id for f in own],
                pages_checked=pages,
            )
        )
    return out
