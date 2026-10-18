"""Country risk figures as structured facts: value, year and source URL. No model reads them.

Two inputs:
  * World Bank Worldwide Governance Indicators (WGI, 2025 revision, source id 3): Political
    Stability, Control of Corruption, Rule of Law, each a 0-100 governance score (higher =
    better governed). Default path: Tavily /extract of the World Bank API URL (a trusted
    worldbank.org page), parsed by code. Retrieval stays on Tavily, like everything else.
    Optional switch ``country_data.wgi_source: worldbank_api`` fetches the same URL directly
    (free, no key); off by default, for comparison only.
  * Transparency International Corruption Perceptions Index (CPI): TI has no API, so the
    official results file is kept in the repo unmodified (data/country/, licence CC BY-ND 4.0)
    and read here.

Verified 2026-10-18: indicator codes GOV_WGI_PV.SC / GOV_WGI_CC.SC / GOV_WGI_RL.SC under
source=3 (the older PV.PER.RNK percentile code is archived); response format saved in
tests/fixtures/country/. INFORM has an API (drmkc.jrc.ec.europa.eu, needs workflow ids);
not used yet.
"""

from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

import httpx2

from .search import SearchClient, SearchError

DATA_DIR = Path(__file__).parent / "data" / "country"
Band = Literal["elevated", "middle", "low"]


@dataclass(frozen=True)
class CountryFigure:
    indicator: str          # e.g. "GOV_WGI_PV.SC" or "CPI"
    label: str              # e.g. "Political Stability (WGI)"
    value: float
    year: int
    scale: str              # e.g. "0-100, higher = better governed"
    source_url: str
    publisher: str
    quote: str              # exact text the value was read from (checked like any quote)
    rank: int | None = None
    of: int | None = None


@dataclass
class CountryDataResult:
    figures: list[CountryFigure] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)   # source URL -> text the figures came from
    titles: dict[str, str] = field(default_factory=dict)
    published: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    extracts_used: int = 0


class CountryDataSource(Protocol):
    def fetch(self, iso2: str, country_name: str) -> CountryDataResult: ...


WGI_LABELS = {
    "GOV_WGI_PV.SC": "Political Stability (WGI)",
    "GOV_WGI_CC.SC": "Control of Corruption (WGI)",
    "GOV_WGI_RL.SC": "Rule of Law (WGI)",
}


def wgi_url(iso2: str, indicators: list[str]) -> str:
    return (f"https://api.worldbank.org/v2/country/{iso2.upper()}/indicator/{';'.join(indicators)}"
            "?format=json&source=3&mrv=1")


def parse_wgi(text: str, url: str, indicators: list[str]) -> tuple[list[CountryFigure], str | None]:
    """Read WGI values from World Bank API JSON (or its text as Tavily returns it)."""
    figures: list[CountryFigure] = []
    updated: str | None = None
    m_upd = re.search(r'"lastupdated"\s*:\s*"(\d{4}-\d{2}-\d{2})"', text)
    if m_upd:
        updated = m_upd.group(1)
    for ind in indicators:
        pat = re.compile(r'"id"\s*:\s*"' + re.escape(ind) + r'".*?"date"\s*:\s*"(\d{4})"\s*,\s*"value"\s*:\s*(-?[0-9.]+)',
                         re.DOTALL)
        m = pat.search(text)
        if not m:
            continue
        year, raw = int(m.group(1)), m.group(2)
        figures.append(CountryFigure(indicator=ind, label=WGI_LABELS.get(ind, ind), value=float(raw), year=year,
                                     scale="0-100, higher = better governed", source_url=url,
                                     publisher="World Bank (WGI)", quote=f'"date":"{year}","value":{raw}'))
    return figures, updated


class TavilyWGI:
    """Default: Tavily extract of the World Bank API URL (trusted worldbank.org), parsed by code."""

    def __init__(self, search: SearchClient, indicators: list[str]) -> None:
        self.search = search
        self.indicators = indicators

    def fetch(self, iso2: str, country_name: str) -> CountryDataResult:
        out = CountryDataResult()
        url = wgi_url(iso2, self.indicators)
        try:
            ext = self.search.extract([url])
        except SearchError as exc:
            out.warnings.append(f"World Bank WGI page could not be read: {exc}")
            return out
        out.extracts_used = 1
        text = ext.pages.get(url, "")
        if not text:
            out.warnings.append(f"World Bank WGI page returned no text: {ext.failed.get(url, 'empty')}")
            return out
        figs, updated = parse_wgi(text, url, self.indicators)
        _store(out, figs, url, text, f"World Bank WGI: {country_name}", updated)
        if not figs:
            out.warnings.append("World Bank WGI page had no values for this country.")
        return out


class DirectWGI:
    """Optional (off by default): the same World Bank API URL fetched directly, for comparison."""

    def __init__(self, indicators: list[str], timeout_s: float = 20.0,
                 transport: httpx2.BaseTransport | None = None) -> None:
        self.indicators = indicators
        self._client = httpx2.Client(timeout=timeout_s, transport=transport)

    def fetch(self, iso2: str, country_name: str) -> CountryDataResult:
        out = CountryDataResult()
        url = wgi_url(iso2, self.indicators)
        try:
            resp = self._client.get(url)
        except httpx2.HTTPError as exc:
            out.warnings.append(f"World Bank API failed: {type(exc).__name__}")
            return out
        if resp.status_code != 200:
            out.warnings.append(f"World Bank API returned HTTP {resp.status_code}")
            return out
        text = resp.text
        figs, updated = parse_wgi(text, url, self.indicators)
        _store(out, figs, url, text, f"World Bank WGI: {country_name}", updated)
        return out


def _store(out: CountryDataResult, figs: list[CountryFigure], url: str, text: str, title: str,
           updated: str | None) -> None:
    if not figs:
        return
    out.figures.extend(figs)
    out.texts[url] = text
    out.titles[url] = title
    if updated:
        out.published[url] = updated


# ---------------------------------------------------------------------------
# TI CPI from the official results file (read with the standard library)
# ---------------------------------------------------------------------------


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def read_xlsx_rows(path: Path, sheet_index: int = 1) -> list[list[str]]:
    """Rows of one sheet as strings. Handles shared strings; no formulas or styles needed."""
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter() if _local(t.tag) == "t") for si in root]
        sheet = ET.fromstring(z.read(f"xl/worksheets/sheet{sheet_index}.xml"))
    rows: list[list[str]] = []
    for row in (r for r in sheet.iter() if _local(r.tag) == "row"):
        vals: list[str] = []
        for c in row:
            v = next((x for x in c if _local(x.tag) == "v"), None)
            if v is None or v.text is None:
                vals.append("")
            elif c.get("t") == "s":
                vals.append(shared[int(v.text)])
            else:
                vals.append(v.text)
        rows.append(vals)
    return rows


class CachedCPI:
    """TI CPI from the official file in data/country/ (no network)."""

    def __init__(self, path: Path, year: int, source_url: str) -> None:
        self.path = path
        self.year = year
        self.source_url = source_url

    def fetch(self, iso2: str, country_name: str) -> CountryDataResult:
        out = CountryDataResult()
        if not self.path.exists():
            out.warnings.append(f"CPI file missing: {self.path.name}")
            return out
        iso3 = iso2_to_iso3(iso2)
        rows = read_xlsx_rows(self.path)
        head = next((i for i, r in enumerate(rows) if "ISO3" in r), None)
        if head is None:
            out.warnings.append("CPI file: header row not found")
            return out
        h = rows[head]
        i_iso, i_name = h.index("ISO3"), 0
        i_score = next(i for i, x in enumerate(h) if x.startswith("CPI") and "score" in x)
        i_rank = next((i for i, x in enumerate(h) if x.startswith("Rank")), None)
        data = [r for r in rows[head + 1:] if len(r) > i_score and r[i_iso]]
        row = next((r for r in data if r[i_iso] == iso3 or r[i_name].lower() == country_name.lower()), None)
        if row is None:
            out.warnings.append(f"CPI file has no row for {country_name or iso2}")
            return out
        score = float(row[i_score])
        rank = int(float(row[i_rank])) if i_rank is not None and row[i_rank] else None
        text = " ".join(x for x in row[: max(i_score, i_rank or 0) + 1] if x)
        out.figures.append(CountryFigure(indicator="CPI", label="Corruption Perceptions Index (TI)", value=score,
                                         year=self.year, scale="0-100, higher = cleaner", source_url=self.source_url,
                                         publisher="Transparency International (CPI)", quote=text, rank=rank,
                                         of=len(data)))
        out.texts[self.source_url] = text
        out.titles[self.source_url] = f"Corruption Perceptions Index {self.year} results: {country_name}"
        return out


def iso2_to_iso3(iso2: str) -> str:
    table = json.loads((DATA_DIR / "iso2_to_iso3.json").read_text(encoding="utf-8"))
    return str(table.get(iso2.upper(), iso2.upper()))


def band_for(value: float, elevated_below: float, low_at_or_above: float) -> Band:
    if value < elevated_below:
        return "elevated"
    if value >= low_at_or_above:
        return "low"
    return "middle"
