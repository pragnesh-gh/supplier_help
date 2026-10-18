from research_agent.identity import resolve_identity
from research_agent.models import IdentityCandidate

URLS = {"S1": "https://a", "S2": "https://b", "S3": "https://c"}


def cand(name, cc, web, src=("S1",)):
    return IdentityCandidate(legal_name=name, country_code=cc, country_name=cc, website=web,
                             description="d", evidence_source_ids=list(src))


RAIL = cand("Veltrava Rail Components GmbH", "DE", "veltrava-rail.example", ("S1",))
MINING = cand("Veltrava Holdings Pty Ltd", "AU", "veltrava-holdings.example", ("S2",))


def test_two_distinct_entities_without_hints_needs_clarification():
    entity, clar = resolve_identity([RAIL, MINING], "Veltrava", None, None, URLS)
    assert entity is None
    assert clar is not None
    assert len(clar.candidates) == 2
    assert clar.question.endswith("?")
    assert {c.country_code for c in clar.candidates} == {"DE", "AU"}


def test_country_hint_disambiguates():
    entity, clar = resolve_identity([RAIL, MINING], "Veltrava", "DE", None, URLS)
    assert clar is None and entity is not None
    assert entity.legal_name == "Veltrava Rail Components GmbH"
    assert entity.evidence_urls == ["https://a"]


def test_country_hint_accepts_name():
    entity, _ = resolve_identity([RAIL, MINING], "Veltrava", "Germany", None, URLS)
    assert entity is not None and entity.country_code == "DE"


def test_website_hint_disambiguates_and_is_kept():
    entity, clar = resolve_identity([RAIL, MINING], "Veltrava", None, "https://www.veltrava-holdings.example/about", URLS)
    assert clar is None and entity is not None
    assert entity.legal_name == "Veltrava Holdings Pty Ltd"


def test_single_candidate_ok():
    entity, clar = resolve_identity([RAIL], "Veltrava", None, None, URLS)
    assert entity is not None and clar is None


def test_duplicate_candidates_of_same_entity_merge():
    dup = cand("Veltrava Rail Components GmbH", "DE", "veltrava-rail.example", ("S3",))
    entity, clar = resolve_identity([RAIL, dup], "Veltrava", None, None, URLS)
    assert entity is not None and clar is None
    assert sorted(entity.evidence_urls) == ["https://a", "https://c"]


def test_candidates_without_valid_evidence_are_ignored():
    ghost = cand("Veltrava Ghost AG", "CH", "ghost.example", ("S99",))
    entity, clar = resolve_identity([RAIL, ghost], "Veltrava", None, None, URLS)
    assert entity is not None and entity.legal_name.startswith("Veltrava Rail")


def test_nothing_found_without_hints_asks_for_details():
    entity, clar = resolve_identity([], "Nonexistent Co", None, None, URLS)
    assert entity is None and clar is not None
    assert clar.candidates == []
    assert "country" in clar.question.lower() and "website" in clar.question.lower()


def test_nothing_found_with_country_and_website_uses_user_input():
    entity, clar = resolve_identity([], "Tiny Rail GmbH", "DE", "tinyrail.example", URLS)
    assert clar is None and entity is not None
    assert entity.confirmed_by == "user_input"
    assert entity.website == "tinyrail.example"


def test_group_entities_on_same_website_do_not_need_clarification():
    parent = cand("Knorr-Bremse AG", "DE", "knorr-bremse.com", ("S1",))
    sub = cand("Knorr-Bremse Systeme für Schienenfahrzeuge GmbH", "DE", "knorr-bremse.com", ("S2",))
    entity, clar = resolve_identity([parent, sub], "Knorr-Bremse", "DE", "knorr-bremse.com", URLS)
    assert clar is None and entity is not None
    assert entity.legal_name == "Knorr-Bremse AG"  # model lists best match first
    assert sorted(entity.evidence_urls) == ["https://a", "https://b"]


def test_same_website_without_website_hint_still_asks():
    parent = cand("Knorr-Bremse AG", "DE", "knorr-bremse.com", ("S1",))
    other = cand("Knorr-Bremse Holding Ltd", "GB", "knorr-bremse.com", ("S2",))
    _, clar = resolve_identity([parent, other], "Knorr-Bremse", None, None, URLS)
    assert clar is not None


def test_hint_matching_nothing_still_asks():
    entity, clar = resolve_identity([RAIL, MINING], "Veltrava", "FR", None, URLS)
    assert entity is None and clar is not None and len(clar.candidates) == 2
