"""Deterministic anti-hallucination checks.

A candidate fact survives only if its quote really appears in the text that Tavily
returned for that URL. Comparison ignores case, whitespace and minor punctuation.
"""

from __future__ import annotations

import re
import unicodedata

_QUOTE_MAP = str.maketrans(
    {
        "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
        "‘": "'", "’": "'", "‚": "'",
        "–": "-", "—": "-", "−": "-", " ": " ",
    }
)
_MIN_QUOTE_CHARS = 12
MAX_QUOTE_WORDS = 25


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).translate(_QUOTE_MAP).lower()
    return re.sub(r"\s+", " ", t).strip()


def _loose(text: str) -> str:
    """Drop all punctuation and markdown so 'said, that' == 'said that'."""
    t = normalize(text)
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def quote_in_text(quote: str, text: str) -> bool:
    if len(normalize(quote)) < _MIN_QUOTE_CHARS:
        return False
    parts = [p for p in re.split(r"\s*(?:\.\.\.|…|\[\.\.\.\])\s*", quote) if p.strip()]
    hay = _loose(text)
    pos = 0
    for part in parts:
        needle = _loose(part)
        if not needle:
            continue
        idx = hay.find(needle, pos)
        if idx < 0:
            return False
        pos = idx + len(needle)
    return True


def quote_context(quote: str, text: str, chars: int = 200) -> str | None:
    """The quote with about ``chars`` characters of page text on each side, whitespace collapsed.
    Found case-insensitively on the start of the quote; None if it cannot be placed."""
    flat = " ".join(text.split())
    head = " ".join(quote.split())[:40]
    if not head:
        return None
    i = flat.lower().find(head.lower())
    if i < 0:
        return None
    start, end = max(0, i - chars), min(len(flat), i + len(" ".join(quote.split())) + chars)
    return ("…" if start > 0 else "") + flat[start:end] + ("…" if end < len(flat) else "")


def word_count(text: str) -> int:
    return len(text.split())


def trim_quote(quote: str, max_words: int = MAX_QUOTE_WORDS) -> str:
    words = quote.split()
    if len(words) <= max_words:
        return quote.strip()
    return " ".join(words[:max_words]) + " …"


# ---------------------------------------------------------------------------
# Syndication check: are two pages the same story?
# ---------------------------------------------------------------------------

SHINGLE_WORDS = 5
# Share of the shorter page's 5-word phrases that must also be in the other page. Containment
# (not Jaccard) because one copy often carries extra site boilerplate or a shorter teaser.
NEAR_DUPLICATE_SHARE = 0.8
# Appendix §A4 guard 4: two pages sharing a passage of 25 or more consecutive words are copies
# (25 = the agent's maximum quote length, so a longer overlap means copying).
COPY_PASSAGE_WORDS = 25


def shingles(text: str, n: int = SHINGLE_WORDS) -> frozenset[str]:
    words = _loose(text).split()
    if len(words) < n:
        return frozenset([" ".join(words)]) if words else frozenset()
    return frozenset(" ".join(words[i : i + n]) for i in range(len(words) - n + 1))


def near_duplicate(a: frozenset[str], b: frozenset[str], share: float = NEAR_DUPLICATE_SHARE) -> bool:
    """True if two pages are copies of the same text (e.g. a syndicated wire story)."""
    if not a or not b:
        return False
    small, big = (a, b) if len(a) <= len(b) else (b, a)
    return len(small & big) / len(small) >= share


def independent_groups(items: list[tuple[str, frozenset[str]]],
                       passages: list[frozenset[str]] | None = None) -> list[list[int]]:
    """Group sources (domain, 5-word shingles) that are not independent: same domain,
    near-identical text, or (with ``passages`` = 25-word shingles) any shared passage of 25 or
    more consecutive words. Returns groups of item indexes; one group = one independent source."""
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            same_domain = items[i][0] == items[j][0]
            shared = bool(passages) and len(passages[i]) > 1 and bool(passages[i] & passages[j])  # type: ignore[index]
            if same_domain or shared or near_duplicate(items[i][1], items[j][1]):
                parent[find(j)] = find(i)
    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())
