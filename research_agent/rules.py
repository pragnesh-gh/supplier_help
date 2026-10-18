"""Deterministic flag rules. The language model never picks a colour; this module does.

All behaviour is driven by ``config/rules.yaml`` so non-coders can read and change it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

from .config import Rules
from .dates import parse_date
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
    capped_unverified: bool = False


def parse_event_date(value: str | None) -> date | None:
    """Parse 'YYYY-MM-DD', 'YYYY-MM', 'YYYY', ISO timestamps or RFC 2822 dates. Anything else -> None."""
    return parse_date(value)


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
    trusted: bool = True,
) -> Classification:
    """Colour one verified fact. ``trusted=False`` means every source for it is unverified:
    then red becomes amber and green becomes neutral, and it can never be a knock-out."""
    rule = rules.event_types[event_type]
    colour: Colour = rule.colour
    notes: list[str] = [f"{event_type} → {colour}"]
    area: UmbrellaId = search_area if rule.area == "from_search" else cast(UmbrellaId, rule.area)

    if severity == "low" and colour == "red":
        colour = "amber"
        notes.append("low severity → amber")

    capped = False
    if not trusted and colour in ("red", "green"):
        new_c: Colour = "amber" if colour == "red" else "neutral"
        notes.append(f"unverified source only: {colour} → {new_c}")
        colour, capped = new_c, True

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

    knockout = bool(rule.knockout and colour == "red" and trusted)
    if knockout:
        notes.append("knock-out rule")
    return Classification(colour=colour, area=area, knockout=knockout, stale=stale, note="; ".join(notes),
                          capped_unverified=capped)


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
    """Most serious first: knock-out, colour, current before stale, trusted before unverified-only,
    severity, then most recent."""
    sev = {"high": 0, "medium": 1, "low": 2}

    def key(f: Flag) -> tuple[int, int, int, int, int, int]:
        d = parse_event_date(f.event_date)
        return (0 if f.knockout else 1, COLOUR_RANK[f.colour], int(f.stale), int(f.trust == "unverified"),
                sev[f.severity], -(d.toordinal() if d else 0))

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
    flags: list[Flag], pages_checked: Mapping[str, int], labels: Mapping[str, str],
    unverified_pages: Mapping[str, int] | None = None, source_trust: Mapping[str, str] | None = None,
) -> list[AreaStatus]:
    """Status per area, from its verified facts:
    red / amber / green from the most serious current fact; "context" when the area has only
    neutral or older (stale) facts; "not_assessed" when no trusted page gave a fact for it.
    Pages read that gave nothing, or only namesake facts, do not count. Neutral or stale facts
    never make an area green. An area with only unverified pages stays "not_assessed" unless
    they produce a watch item."""
    out: list[AreaStatus] = []
    unverified_pages = unverified_pages or {}
    source_trust = source_trust or {}
    for area in UMBRELLAS:
        area_flags = [f for f in flags if f.area == area]
        backing = {sid for f in area_flags for sid in f.source_ids}
        t_used = len([s for s in backing if source_trust.get(s, "trusted") == "trusted"])
        u_used = len(backing) - t_used
        own = sort_flags([f for f in area_flags if f.colour != "neutral"])
        pages = pages_checked.get(area, 0)
        upages = unverified_pages.get(area, 0)
        status: Literal["red", "amber", "green", "context", "not_assessed"]
        neutral = sort_flags([f for f in area_flags if f.colour == "neutral" and f.trust == "trusted"])
        if own:
            top = own[0]
            status = top.colour if top.colour != "neutral" else "context"
            finding = top.summary
        elif neutral:
            # Only neutral or older facts: recorded as context. Never "No issues found":
            # an old settled case or a company-disclosed risk is not evidence of no issues.
            own = neutral[:1]
            status = "context"
            finding = neutral[0].summary
        else:
            status = "not_assessed"
            finding = "Not assessed — no trusted source returned evidence."
            if pages > 0:
                finding = (f"Not assessed — {_plural(pages, 'trusted page')} read, none gave usable evidence "
                           "about this company.")
        out.append(
            AreaStatus(
                area=area,
                label=labels.get(area, area),
                status=status,
                finding=finding,
                flag_ids=[f.id for f in own],
                pages_checked=pages,
                unverified_pages_checked=upages,
                trusted_pages_used=t_used,
                unverified_pages_used=u_used,
            )
        )
    return out


def _plural(n: int, singular: str) -> str:
    return f"{n} {singular if n == 1 else singular + 's'}"


# Headline points (report section 1 and the chat TL;DR). The first live run (Knorr-Bremse,
# 2026-10-18) showed five green financial points and nothing on the other areas, so a buyer
# could not see what was checked elsewhere. The points now cover areas, not one area.
MIN_POINTS, MAX_POINTS, MAX_ADVERSE_POINTS, MAX_POINTS_PER_AREA = 3, 5, 4, 2


def headline_points(flags: list[Flag], known_source_ids: set[str], rules: Rules | None = None) -> list[Flag]:
    """Red flags, then watch items, then strengths ("checked, nothing adverse found"), then
    older or resolved adverse matters ("context"), at most 2 points per area and 5 in total.

    Within each colour, an area without a point comes first, so serious items from different
    areas are shown before a second item from the same area. At most 4 red flags and watch
    items. Strengths: one per area not yet shown (then a second per area only to reach 3
    points). An older or resolved adverse matter (a red or amber event type that went stale,
    e.g. a 2018 settlement) is shown only for an area that has no other point, when there is
    room, so a checked area is visible. Only flags that cite a known source are used, so every
    point has a citation. Missing areas are named separately as "Not assessed"."""
    cited = [f for f in sort_flags(flags) if any(sid in known_source_ids for sid in f.source_ids)]
    chosen: list[Flag] = []
    per_area: dict[str, int] = {}

    def take(pool: list[Flag], limit: int, rounds: tuple[int, ...]) -> None:
        for allowed_before in rounds:  # 0: areas without a point; 1: a second point per area
            for f in pool:
                if len(chosen) >= limit:
                    return
                n = per_area.get(f.area, 0)
                if f in chosen or n > allowed_before or n >= MAX_POINTS_PER_AREA:
                    continue
                chosen.append(f)
                per_area[f.area] = n + 1

    for colour in ("red", "amber"):
        take([f for f in cited if f.colour == colour], MAX_ADVERSE_POINTS, (0, 1))
    greens = [f for f in cited if f.colour == "green"]
    take(greens, MAX_POINTS, (0,))
    take(greens, MIN_POINTS, (1,))
    if rules is None:
        from .config import load_rules
        rules = load_rules()

    def older_adverse(f: Flag) -> bool:
        rule = rules.event_types.get(f.event_type)
        return (f.colour == "neutral" and f.stale and f.trust == "trusted" and rule is not None
                and rule.colour in ("red", "amber"))

    take([f for f in cited if older_adverse(f)], MAX_POINTS, (0,))
    order = {f.id: i for i, f in enumerate(cited)}
    return sorted(chosen, key=lambda f: (COLOUR_RANK[f.colour], order[f.id]))
