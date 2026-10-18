"""Date parsing for dates that come from Tavily, the models or page text.

Tavily's ``published_date`` can be ISO ("2026-07-29", "2026-07-29T05:00:51Z") or RFC 2822
("Wed, 29 Jul 2026 05:00:51 GMT"). Models return "YYYY-MM-DD", "YYYY-MM" or "YYYY".
Everything is turned into ISO text here, once, so the report, the staleness rules and the
same-event (corroboration) check all compare the same thing.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime

_PARTIAL = re.compile(r"\s*(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?\s*")
_ISO_PREFIX = re.compile(r"\s*(\d{4})-(\d{2})-(\d{2})[T ]")


def _valid(y: int, m: int, d: int) -> bool:
    try:
        date(y, m, d)
    except ValueError:
        return False
    return 1900 <= y <= 2100


def normalize_date(value: str | None) -> str | None:
    """'YYYY', 'YYYY-MM' or 'YYYY-MM-DD' (keeping the precision given), from ISO dates,
    ISO timestamps or RFC 2822 strings. Anything unparseable -> None."""
    if not value or not value.strip():
        return None
    v = value.strip()
    m = _PARTIAL.fullmatch(v)
    if m:
        y, mo, d = int(m.group(1)), m.group(2), m.group(3)
        if not _valid(y, int(mo or 1), int(d or 1)):
            return None
        if d:
            return f"{y:04d}-{int(mo or 1):02d}-{int(d):02d}"
        if mo:
            return f"{y:04d}-{int(mo):02d}"
        return f"{y:04d}"
    m2 = _ISO_PREFIX.match(v)
    if m2:
        y, mo2, d2 = (int(x) for x in m2.groups())
        return f"{y:04d}-{mo2:02d}-{d2:02d}" if _valid(y, mo2, d2) else None
    try:
        dt = parsedate_to_datetime(v)
    except (TypeError, ValueError, IndexError):
        dt = None
    if isinstance(dt, datetime) and _valid(dt.year, dt.month, dt.day):
        return dt.date().isoformat()
    return None


def parse_date(value: str | None) -> date | None:
    """A ``date`` for comparisons; a missing month or day counts as the 1st."""
    iso = normalize_date(value)
    if iso is None:
        return None
    parts = [int(p) for p in iso.split("-")]
    while len(parts) < 3:
        parts.append(1)
    return date(parts[0], parts[1], parts[2])


def month_key(value: str | None) -> str | None:
    """'YYYY-MM' (or 'YYYY' when only the year is known), used to match the same event."""
    iso = normalize_date(value)
    return iso[:7] if iso else None
