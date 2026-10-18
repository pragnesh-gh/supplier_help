"""Country figures from World Bank WGI (fixture = a real API response) and the TI CPI file."""

import json
from pathlib import Path

import httpx2

from research_agent.country_data import (
    DATA_DIR,
    CachedCPI,
    DirectWGI,
    TavilyWGI,
    band_for,
    iso2_to_iso3,
    parse_wgi,
    wgi_url,
)
from research_agent.search import ExtractResponse

FIX = Path(__file__).parent / "fixtures" / "country" / "worldbank_wgi_DE_2025.json"
INDS = ["GOV_WGI_PV.SC", "GOV_WGI_CC.SC", "GOV_WGI_RL.SC"]


def test_parse_real_world_bank_response():
    text = FIX.read_text(encoding="utf-8")
    json.loads(text)  # the fixture is the API's own JSON
    figs, updated = parse_wgi(text, "u", INDS)
    by = {f.indicator: f for f in figs}
    assert set(by) == set(INDS) and updated == "2026-09-25"
    assert by["GOV_WGI_PV.SC"].year == 2025 and round(by["GOV_WGI_PV.SC"].value, 1) == 69.3
    assert round(by["GOV_WGI_CC.SC"].value, 1) == 81.9 and round(by["GOV_WGI_RL.SC"].value, 1) == 85.1
    assert all(f.quote in text for f in figs)  # the quote is exact text from the response


def test_parse_tolerates_reformatted_text():
    text = FIX.read_text(encoding="utf-8")
    pretty = json.dumps(json.loads(text), indent=2)  # what an extractor might return
    figs, _ = parse_wgi(pretty, "u", INDS)
    assert len(figs) == 3


def test_tavily_path_extracts_the_world_bank_url():
    class FakeExtract:
        def __init__(self):
            self.urls = []

        def search(self, request):  # pragma: no cover
            return []

        def extract(self, urls, query=None):
            self.urls += urls
            return ExtractResponse(pages={urls[0]: FIX.read_text(encoding="utf-8")})

    fake = FakeExtract()
    res = TavilyWGI(fake, INDS).fetch("DE", "Germany")
    assert fake.urls == [wgi_url("DE", INDS)]
    assert fake.urls[0].startswith("https://api.worldbank.org/v2/country/DE/indicator/GOV_WGI_PV.SC;")
    assert len(res.figures) == 3 and res.extracts_used == 1 and not res.warnings


def test_direct_api_switch_uses_same_url():
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        return httpx2.Response(200, text=FIX.read_text(encoding="utf-8"))

    res = DirectWGI(INDS, transport=httpx2.MockTransport(handler)).fetch("DE", "Germany")
    assert "source=3" in seen["url"] and len(res.figures) == 3


def test_cpi_from_official_file():
    res = CachedCPI(DATA_DIR / "CPI2025_Results.xlsx", 2025, "https://www.transparency.org/en/cpi/2025").fetch("DE", "Germany")
    f = res.figures[0]
    assert f.indicator == "CPI" and f.value == 77 and f.rank == 10 and f.of == 182 and f.year == 2025
    assert f.quote in res.texts[f.source_url]


def test_bands_are_thirds_of_the_scale():
    assert band_for(20, 33.3, 66.7) == "elevated"
    assert band_for(50, 33.3, 66.7) == "middle"
    assert band_for(66.7, 33.3, 66.7) == "low"


def test_iso_map():
    assert iso2_to_iso3("de") == "DEU" and iso2_to_iso3("GB") == "GBR"
