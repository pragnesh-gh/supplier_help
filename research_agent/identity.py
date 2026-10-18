"""Deterministic identity resolution from model-proposed candidates.

The gatherer model lists candidate legal entities found in trusted search results.
This module decides, without the model, whether the buyer's input points to exactly
one entity (status ok) or whether the buyer must choose (needs_clarification).
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from .config import domain_of
from .models import ClarificationRequest, ConfirmedEntity, IdentityCandidate

# Small lookup so "Germany" and "DE" both work; anything else compares by name.
_COUNTRY_NAMES = {
    "DE": "germany", "AT": "austria", "CH": "switzerland", "FR": "france", "IT": "italy", "ES": "spain",
    "NL": "netherlands", "BE": "belgium", "PL": "poland", "CZ": "czechia", "SE": "sweden", "GB": "united kingdom",
    "UK": "united kingdom", "US": "united states", "IN": "india", "CN": "china", "JP": "japan", "AU": "australia",
    "CA": "canada", "TR": "turkey", "HU": "hungary", "RO": "romania", "DK": "denmark", "FI": "finland",
    "NO": "norway", "PT": "portugal", "KR": "south korea", "BR": "brazil",
}

_LEGAL_SUFFIX = re.compile(
    r"\b(gmbh|ag|se|kg|kgaa|co|ltd|limited|plc|inc|corp|corporation|llc|sa|sas|spa|s\.p\.a|bv|nv|pty|oy|ab|as|group|holding|holdings)\b\.?",
    re.IGNORECASE,
)


def _norm_name(name: str) -> str:
    n = _LEGAL_SUFFIX.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def _country_matches(hint: str, cand: IdentityCandidate) -> bool:
    h = hint.strip().lower()
    code = cand.country_code.strip().upper()
    if not h:
        return True
    if len(h) == 2:
        return h.upper() == code or (h.upper() == "UK" and code == "GB")
    return h == cand.country_name.strip().lower() or _COUNTRY_NAMES.get(code, "") == h


def _website_matches(hint: str, cand: IdentityCandidate) -> bool:
    h, c = domain_of(hint), domain_of(cand.website)
    return bool(h and c) and (h == c or h.endswith("." + c) or c.endswith("." + h))


def _to_entity(c: IdentityCandidate, urls: list[str], website_hint: str | None) -> ConfirmedEntity:
    return ConfirmedEntity(
        legal_name=c.legal_name.strip(),
        country_code=c.country_code.strip().upper(),
        country_name=c.country_name.strip(),
        website=domain_of(website_hint) if website_hint else domain_of(c.website),
        description=c.description.strip(),
        evidence_urls=urls,
    )


def resolve_identity(
    candidates: list[IdentityCandidate],
    company: str,
    country: str | None,
    website: str | None,
    source_urls: Mapping[str, str],
) -> tuple[ConfirmedEntity | None, ClarificationRequest | None]:
    # 1. Keep only candidates backed by real source blocks; merge duplicates of the same entity.
    merged: dict[tuple[str, str], tuple[IdentityCandidate, list[str]]] = {}
    for c in candidates:
        urls = [source_urls[s] for s in c.evidence_source_ids if s in source_urls]
        if not urls or not c.legal_name.strip():
            continue
        key = (_norm_name(c.legal_name), c.country_code.strip().upper())
        if key in merged:
            prev, prev_urls = merged[key]
            merged[key] = (prev, prev_urls + [u for u in urls if u not in prev_urls])
        else:
            merged[key] = (c, urls)
    pool = list(merged.values())

    # 2. Apply the buyer's hints.
    narrowed = pool
    if website:
        # Website is the strongest hint; if no candidate lists a website that matches, ignore it.
        by_site = [p for p in narrowed if _website_matches(website, p[0])]
        narrowed = by_site or narrowed
    if country:
        narrowed = [p for p in narrowed if _country_matches(country, p[0])]

    # The buyer named the website and every remaining candidate uses it: one corporate group.
    # Take the model's first (best-matching) candidate and keep all evidence.
    if website and len(narrowed) > 1 and all(_website_matches(website, p[0]) for p in narrowed):
        all_urls = list(dict.fromkeys(u for _, urls in narrowed for u in urls))
        narrowed = [(narrowed[0][0], all_urls)]

    if len(narrowed) == 1:
        c, urls = narrowed[0]
        return _to_entity(c, urls, website), None

    # 3. Nothing found in sources but the buyer gave enough to proceed.
    if not pool and country and website:
        return (
            ConfirmedEntity(
                legal_name=company.strip(), country_code=country.strip().upper() if len(country.strip()) == 2 else "",
                country_name=country.strip() if len(country.strip()) != 2 else _COUNTRY_NAMES.get(country.strip().upper(), "").title(),
                website=domain_of(website), confirmed_by="user_input",
            ),
            None,
        )

    if not pool:
        return None, ClarificationRequest(
            question=(
                f"We could not identify “{company}” in trusted sources. "
                "Can you add the country and the company's official website?"
            ),
            candidates=[],
        )

    # 4. Several distinct entities remain (or hints matched none): ask the buyer.
    shown = narrowed if len(narrowed) > 1 else pool
    ents = [_to_entity(c, urls, None) for c, urls in shown]
    options = "; ".join(
        f"{e.legal_name} ({e.country_name or e.country_code or 'country unknown'})" for e in ents[:3]
    )
    return None, ClarificationRequest(
        question=f"Several companies match “{company}” — which one do you mean: {options}?",
        candidates=ents,
    )
