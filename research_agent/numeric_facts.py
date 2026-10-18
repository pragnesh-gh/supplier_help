"""Numbers for the scoring step: check them like quotes, parse them, assemble ScoringInputs.

The gatherer lists numbers it sees on a page (credit rating, accounts lines, fine amount,
injury rate, EcoVadis score), each with an exact quote. Code then decides:
  1. the quote must be in the page text (same check as for facts);
  2. the value, exactly as written, must be inside the quote (a number the quote does not
     contain is never used); a rating's agency must be named in the quote too;
  3. the page must be about the confirmed company: at least one fact from it passed the
     verifier as this entity or its group;
  4. the value must parse (thousand separators, decimal comma, million/billion words).
Only then is it used. Unverified numbers are kept but marked, and the scorer ignores them.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .dates import normalize_date, parse_date
from .models import Flag, NumberOut, NumericFact, Source
from .scoring_inputs import (
    AltmanInputs,
    CountryIndexInput,
    CreditRatingInput,
    EcoVadisInput,
    Evidence,
    FineInput,
    InjuryRateInput,
    ScoringInputs,
    SourceReliability,
)
from .verification import normalize, quote_in_text

AGENCIES = {"S&P": ("s&p", "standard & poor", "standard and poor"), "Moody's": ("moody",), "Fitch": ("fitch",)}
_SCALE = [
    (re.compile(r"\b(billion|billions|bn|bln|mrd|milliarden?|md)\b", re.I), 1e9),
    (re.compile(r"\b(million|millions|mn|mio|mill|m)\b", re.I), 1e6),
    (re.compile(r"\b(thousand|thousands|tsd|k)\b|\bt(eur|usd|chf|gbp)\b", re.I), 1e3),
]
_CURRENCY = [("EUR", ("eur", "€", "euro")), ("USD", ("usd", "us$", "$", "dollar")), ("GBP", ("gbp", "£")),
             ("CHF", ("chf",)), ("JPY", ("jpy", "¥", "yen")), ("CNY", ("cny", "rmb", "yuan")), ("SEK", ("sek",))]
ACCOUNT_LINES = ("current_assets", "current_liabilities", "retained_earnings", "ebit", "total_equity", "total_assets")
FINE_EVENTS = ("regulatory_fine", "antitrust_settlement", "major_lawsuit")
# Editorial-accountability signals on a page (appendix §A4 step 2, grade C): corrections policy,
# editorial standards or ethics code, a masthead or legal notice naming the editors, IFCN.
_EDITORIAL = re.compile(
    r"corrections? (policy|polic(y|ies)|page)|editorial (standards|policy|guidelines|code)|code of ethics|"
    r"ethics policy|ifcn|editor[- ]in[- ]chief|impressum|chefredakt|verantwortlich (i\. ?s\. ?d\.|im sinne)|"
    r"rédacteur en chef|directeur de la publication|direttore responsabile|director editorial",
    re.IGNORECASE)


_GERMAN_UNIT = re.compile(r"\b(mio|mrd|tsd|millionen|milliarden)\b", re.IGNORECASE)


def parse_number(value: str, german: bool = False) -> float | None:
    """'9,523.4' -> 9523.4; '9.523,4' -> 9523.4; '4,2' -> 4.2; '7,887' -> 7887; '(12.5)' -> -12.5.
    A single '.' is a decimal point, except in German figures ('7.887 Mio. EUR' -> 7887)."""
    v = value.strip().replace("\u2212", "-").replace("\u00a0", "").replace(" ", "").replace("'", "")
    neg = (v.startswith("(") and v.endswith(")")) or v.startswith("-")
    v = re.sub(r"[^\d.,]", "", v.strip("()-+"))
    if not v or not v[0].isdigit():
        return None
    if "," in v and "." in v:
        dec = "," if v.rfind(",") > v.rfind(".") else "."
        v = v.replace("." if dec == "," else ",", "").replace(",", ".")
    elif "," in v:
        parts = v.split(",")
        v = v.replace(",", "") if all(len(p) == 3 for p in parts[1:]) else v.replace(",", ".")
    elif v.count(".") > 1 or (german and v.count(".") == 1 and len(v.split(".")[1]) == 3):
        v = v.replace(".", "")
    try:
        x = float(v)
    except ValueError:
        return None
    return -x if neg else x


def scale_of(unit: str) -> float:
    for pat, mult in _SCALE:
        if pat.search(unit):
            return mult
    return 1.0


def currency_of(unit: str) -> str:
    u = unit.lower()
    for code, keys in _CURRENCY:
        if any(k in u for k in keys):
            return code
    return ""


def value_in_quote(value: str, quote: str) -> bool:
    """The value, exactly as written (spaces ignored), is part of the quote."""
    v = re.sub(r"\s+", "", normalize(value))
    q = re.sub(r"\s+", "", normalize(quote))
    if not v:
        return False
    if re.fullmatch(r"[a-z]{1,4}[0-9+-]*", v):  # a rating symbol: whole token, case-sensitive
        return re.search(r"(?<![A-Za-z0-9])" + re.escape(value.strip()) + r"(?![A-Za-z0-9+-])", quote) is not None
    # A number must match whole: '9,523' is not in '9,523.4', and '52' is not in '520'.
    return re.search(r"(?<![\d.,])" + re.escape(v) + r"(?![\d]|[.,]\d)", q) is not None


def agency_of(detail: str, quote: str) -> str | None:
    d, q = detail.lower(), quote.lower()
    for name, keys in AGENCIES.items():
        if any(k in d for k in keys) and any(k in q for k in keys):
            return name
    return None


def check_number(n: NumberOut, page_text: str, source: Source) -> NumericFact:
    """Steps 1, 2 and 4 of the module docstring (step 3 needs the verified facts; see accept_pages)."""
    fact = NumericFact(kind=n.kind, value=n.value.strip(), unit=n.unit.strip(), period=normalize_date(n.period),
                       detail=n.detail.strip(), outlook=n.outlook.strip(), quote=n.quote.strip(), source_id=source.id,
                       trust=source.trust, company_stated=source.tier == "company_own")

    def reject(reason: str) -> NumericFact:
        fact.accepted, fact.reject_reason = False, reason
        return fact

    if not quote_in_text(n.quote, page_text):
        return reject("quote not found in source text")
    if not value_in_quote(n.value, n.quote):
        return reject("value not in the quote")
    if n.kind == "credit_rating":
        agency = agency_of(n.detail, n.quote)
        if agency is None:
            return reject("rating agency not named in the quote")
        fact.detail = agency
        return fact
    x = parse_number(n.value, german=bool(_GERMAN_UNIT.search(f"{n.unit} {n.quote}")))
    if x is None:
        return reject("value is not a number")
    if n.kind in ("injury_rate", "ecovadis_score"):
        fact.amount = x
        if n.kind == "ecovadis_score" and not 0 <= x <= 100:
            return reject("EcoVadis score outside 0-100")
        if n.kind == "injury_rate" and n.detail.upper() not in ("TRIR", "DART", "LTIFR"):
            return reject("injury metric not TRIR, DART or LTIFR")
        fact.detail = n.detail.upper() if n.kind == "injury_rate" else ""
        return fact
    cur = currency_of(n.unit) or currency_of(n.quote)
    if not cur:
        return reject("currency not stated")
    fact.currency = cur
    fact.amount = x * scale_of(n.unit or n.quote)
    return fact


def accept_pages(facts: list[NumericFact], flags: Sequence[Flag]) -> None:
    """Step 3: numbers count only from pages that gave a verified fact about this company."""
    about = {sid for f in flags for sid in f.source_ids}
    for f in facts:
        if f.accepted and f.source_id not in about:
            f.accepted, f.reject_reason = False, "page gave no verified fact about this company"


def source_reliability(sources: Sequence[Source], texts: Mapping[str, str]) -> dict[str, SourceReliability]:
    """Grade per unverified source: C if the page shows editorial accountability, else D."""
    out: dict[str, SourceReliability] = {}
    for s in sources:
        if s.trust != "unverified":
            continue
        out[s.id] = "C" if _EDITORIAL.search(texts.get(s.id, "")) else "D"
    return out


def _evidence(f: NumericFact, sources: Mapping[str, Source], quote: str | None = None) -> Evidence:
    s = sources[f.source_id]
    return Evidence(source_url=s.url, quote=quote or f.quote, date=f.period or s.published_date, trust=f.trust,
                    source_id=s.id, company_stated=f.company_stated)


def _latest(items: list[NumericFact]) -> NumericFact | None:
    def key(f: NumericFact) -> tuple[int, str]:
        d = parse_date(f.period)
        return (d.toordinal() if d else 0, f.source_id)
    return max(items, key=key) if items else None


def build_inputs(numbers: list[NumericFact], flags: Sequence[Flag], sources: Sequence[Source],
                 country: Sequence[dict[str, Any]], texts: Mapping[str, str],
                 injury_benchmarks: Mapping[str, Mapping[str, Any]], hq_country: str) -> ScoringInputs:
    """Assemble ScoringInputs from accepted numbers, country figures and source grades."""
    src = {s.id: s for s in sources}
    ok = [n for n in numbers if n.accepted]

    ratings: dict[str, CreditRatingInput] = {}
    for n in sorted((n for n in ok if n.kind == "credit_rating"), key=lambda n: (n.period or "", n.source_id)):
        ratings[n.detail] = CreditRatingInput(agency=n.detail, rating=n.value, outlook=n.outlook or None,
                                              evidence=_evidence(n, src))

    altman = _altman(ok, src, texts)
    revenue = _latest([n for n in ok if n.kind == "revenue" and n.trust == "trusted"])

    fines: list[FineInput] = []
    for fl in flags:
        if fl.event_type not in FINE_EVENTS or revenue is None:
            continue
        amt = next((n for n in ok if n.kind == "fine_amount" and n.source_id in fl.source_ids
                    and n.currency == revenue.currency and n.amount), None)
        if amt is not None and revenue.amount:
            fines.append(FineInput(flag_id=fl.id, amount=abs(amt.amount or 0.0), revenue=revenue.amount,
                                   currency=revenue.currency, evidence=_evidence(amt, src)))

    injury = None
    for n in sorted((n for n in ok if n.kind == "injury_rate"), key=lambda n: (n.period or "", n.source_id), reverse=True):
        bench = injury_benchmarks.get(n.detail)
        year = parse_date(n.period)
        if bench and year and n.amount and n.amount > 0:
            injury = InjuryRateInput(
                metric=n.detail, company_rate=n.amount, benchmark_rate=float(bench["rate"]),
                benchmark_label=str(bench["label"]), year=year.year, evidence=_evidence(n, src),
                benchmark_evidence=Evidence(source_url=str(bench["url"]), quote=str(bench["label"]),
                                            date=str(bench.get("year", "")) or None, trust="trusted"))
            break

    eco = _latest([n for n in ok if n.kind == "ecovadis_score"])
    ecovadis = EcoVadisInput(score=eco.amount or 0.0, evidence=_evidence(eco, src)) if eco else None

    indices: list[CountryIndexInput] = []
    for c in country:
        if c.get("indicator") == "GOV_WGI_PV.SC" and c.get("source_id"):
            s = src[c["source_id"]]
            indices.append(CountryIndexInput(
                index="wgi_political_stability", country_code=hq_country.upper(), value=float(c["value"]),
                year=int(c["year"]), basis="hq",
                evidence=Evidence(source_url=s.url, quote=str(c["quote"]), date=s.published_date, trust=s.trust,
                                  source_id=s.id)))

    return ScoringInputs(credit_ratings=tuple(ratings[a] for a in sorted(ratings)), altman=altman, fines=tuple(fines),
                         injury_rate=injury, ecovadis=ecovadis, country_indices=tuple(indices),
                         source_reliability=source_reliability(sources, texts))


def _altman(ok: list[NumericFact], src: Mapping[str, Source], texts: Mapping[str, str]) -> AltmanInputs | None:
    """All lines from one page, one period and one currency; latest complete period wins.
    Total liabilities = total assets - total equity when the page does not state it."""
    groups: dict[tuple[str, str, str], dict[str, NumericFact]] = {}
    for n in ok:
        if n.trust != "trusted" or n.kind not in (*ACCOUNT_LINES, "total_liabilities") or n.amount is None:
            continue
        groups.setdefault((n.source_id, n.period or "", n.currency), {}).setdefault(n.kind, n)
    best: tuple[str, AltmanInputs] | None = None
    for (sid, period, cur), lines in groups.items():
        if not period or not all(k in lines for k in ACCOUNT_LINES):
            continue
        ta, eq = lines["total_assets"].amount or 0.0, lines["total_equity"].amount or 0.0
        tl = lines["total_liabilities"].amount if "total_liabilities" in lines else ta - eq
        if not tl or tl <= 0 or ta <= 0:
            continue
        text = texts.get(sid, "")
        used = sorted(lines.values(), key=lambda n: _pos(text, n.quote))
        quote = " … ".join(n.quote for n in used)  # in page order, so the joined quote still checks
        first = used[0]
        a = AltmanInputs(fiscal_year_end=period, current_assets=lines["current_assets"].amount or 0.0,
                         current_liabilities=lines["current_liabilities"].amount or 0.0,
                         retained_earnings=lines["retained_earnings"].amount or 0.0, ebit=lines["ebit"].amount or 0.0,
                         book_equity=eq, total_liabilities=tl, total_assets=ta, currency=cur,
                         evidence=_evidence(first, src, quote=quote))
        if best is None or period > best[0]:
            best = (period, a)
    return best[1] if best else None


def _pos(text: str, quote: str) -> int:
    i = normalize(text).find(normalize(quote)[:40])
    return i if i >= 0 else 10**9
