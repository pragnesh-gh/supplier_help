"""Typed numeric inputs for the scoring step (docs/research/facts-to-scores-appendix.md §A2).

Event-based scores read the existing :class:`~research_agent.models.Flag` objects and their
grading signals. Index-based scores need numbers (a credit rating, annual-accounts lines,
a WGI value, ...). This module defines those numbers. Every value carries its evidence (URL,
exact quote, date, trust) so the facts pipeline can fill it with the same quote check it
uses for flags. Nothing here calls a model or the network.

Rules the scorer applies to these inputs:
  * Only ``trust == "trusted"`` inputs are used. An unverified number is listed as "not used"
    in the breakdown: the Admiralty-code discount (§A4) is defined for event facts, not
    for numbers that set a whole base score.
  * Inputs never override a knock-out; they only set a score's base.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import Trust

Agency = Literal["S&P", "Moody's", "Fitch"]
CountryIndex = Literal["wgi_political_stability", "inform_human_hazard", "inform_natural_hazard"]
CountryBasis = Literal["site", "hq"]
InjuryMetric = Literal["TRIR", "DART", "LTIFR"]
LicensedEsgProvider = Literal["sustainalytics", "msci"]
SourceReliability = Literal["B", "C", "D"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evidence(_In):
    """Where a number comes from. ``quote`` must be copied from the page (quote-checked upstream)."""

    source_url: str = Field(min_length=1)
    quote: str = Field(min_length=1, description="Exact words from the source that state the value.")
    date: str | None = Field(default=None, description="Publication or as-of date, YYYY-MM-DD / YYYY-MM / YYYY.")
    trust: Trust = "trusted"
    source_id: str | None = Field(default=None, description="Id of the Source in result.sources, if any.")
    company_stated: bool = False


class CreditRatingInput(_In):
    agency: Agency
    rating: str = Field(min_length=1, description="Long-term issuer rating as published, e.g. 'A-', 'Baa3'.")
    outlook: str | None = Field(default=None, description="Shown, not scored (appendix §A2).")
    evidence: Evidence


class AltmanInputs(_In):
    """Lines from one set of annual accounts, all in the same currency and unit."""

    fiscal_year_end: str = Field(min_length=4, description="YYYY-MM-DD or YYYY.")
    current_assets: float
    current_liabilities: float
    retained_earnings: float
    ebit: float
    book_equity: float
    total_liabilities: float = Field(gt=0)
    total_assets: float = Field(gt=0)
    currency: str = ""
    evidence: Evidence


class FineInput(_In):
    """Amount of the fine or claim behind one flag, and the company's annual revenue."""

    flag_id: str
    amount: float = Field(ge=0)
    revenue: float = Field(gt=0, description="Annual revenue, same currency and unit as amount.")
    currency: str = ""
    evidence: Evidence


class InjuryRateInput(_In):
    metric: InjuryMetric
    company_rate: float = Field(gt=0)
    benchmark_rate: float = Field(gt=0, description="Same metric, same sector (e.g. BLS NAICS 3365 TRIR 2.4).")
    benchmark_label: str = Field(min_length=1, description="e.g. 'BLS SOII 2024, NAICS 3365, TRIR'.")
    year: int
    evidence: Evidence
    benchmark_evidence: Evidence


class EcoVadisInput(_In):
    score: float = Field(ge=0, le=100)
    evidence: Evidence


class LicensedEsgInput(_In):
    """Used only if the licence switch for the provider is on (scoring_method.yaml, Decision 2)."""

    provider: LicensedEsgProvider
    value: str = Field(min_length=1, description="Sustainalytics risk score as a number string, or MSCI letter.")
    evidence: Evidence


class SecurityRatingInput(_In):
    """SecurityScorecard 0-100 (higher = better). Used only if licensed."""

    score: float = Field(ge=0, le=100)
    evidence: Evidence


class CountryIndexInput(_In):
    index: CountryIndex
    country_code: str = Field(min_length=2, max_length=2)
    value: float = Field(description="WGI governance score 0-100, or INFORM category 0-10, as published.")
    year: int
    basis: CountryBasis = Field(description="'site' = a supplying site's country; 'hq' = headquarters country.")
    share: float = Field(default=1.0, gt=0, description="Relative weight of this site (sites only).")
    ci_low: float | None = None
    ci_high: float | None = None
    evidence: Evidence


class ScoringInputs(_In):
    credit_ratings: tuple[CreditRatingInput, ...] = ()
    altman: AltmanInputs | None = None
    fines: tuple[FineInput, ...] = ()
    injury_rate: InjuryRateInput | None = None
    ecovadis: EcoVadisInput | None = None
    licensed_esg: tuple[LicensedEsgInput, ...] = ()
    security_rating: SecurityRatingInput | None = None
    country_indices: tuple[CountryIndexInput, ...] = ()
    source_reliability: dict[str, SourceReliability] = Field(
        default_factory=dict,
        description="Optional Admiralty reliability grade per unverified source id, set by code from the "
                    "page's editorial-accountability signals (§A4 step 2). Missing = 'D'.")
