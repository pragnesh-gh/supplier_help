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


def word_count(text: str) -> int:
    return len(text.split())


def trim_quote(quote: str, max_words: int = MAX_QUOTE_WORDS) -> str:
    words = quote.split()
    if len(words) <= max_words:
        return quote.strip()
    return " ".join(words[:max_words]) + " …"
