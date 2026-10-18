"""Deterministic facts-to-scores method (docs/research/facts-to-scores.md + -appendix.md).

Scale: 0 = no risk, 100 = maximum risk (docs/risk_criteria_description.md). The 18 dataset
sub-scores are scored first, then the six areas, then the total, with Siemens's weights
(exact fit to the dataset, appendix §A1). Constants live in ``config/scoring_method.yaml``.
Every rubric constant is *derived here* from the three anchors, so it cannot drift.

Event rubric (appendix §A3), per sub-score:
    score = 100 - (100 - base) * Π (1 - p/100),   p = P_colour * decay * source_weight
    P_colour = 100 * (1 - (100 - anchor) / (100 - base_nothing_adverse))
    decay    = 0.5 ** (age / (k * stale_years)),  k = ln 2 / ln(P_red / P_amber)
so one fresh trusted red event gives 50, one amber gives 25, and at its staleness date a red
event weighs exactly what a fresh amber does (the rules.yaml "step down one colour").

Guarantees:
  * An area or sub-score with no evidence is ``None`` ("Not assessed"), never 0.
  * Unverified-only facts never cause a knock-out and add at most one Level band to a score.
  * Overrides (appendix §A5): a current, trusted red fact lifts its area to at least High (50);
    a trusted knock-out lifts the total to at least Critical (75). Both are breakdown lines.
  * The same inputs (including ``as_of``) give byte-identical output.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import CONFIG_DIR, ConfigError, Rules, ScoringConfig, domain_of, load_rules, load_scoring, load_settings
from .models import EVENT_TYPES, UMBRELLAS, AreaScore, AreaStatus, Colour, Coverage, Flag, ScoreCard, ScoreLevel, \
    Source, UmbrellaId
from .rules import parse_event_date
from .scoring_inputs import AltmanInputs, CountryIndex, CountryIndexInput, CreditRatingInput, Evidence, ScoringInputs

NOT_SCORED = "not scored yet"
NOT_ASSESSED = "not scored: area not assessed (no evidence), so no score is given, not even 0"
NO_CONFIG = "not scored yet: no scoring config given"

DEFAULT_LEVELS: list[tuple[ScoreLevel, int]] = [("Low", 0), ("Medium", 25), ("High", 50), ("Critical", 75)]
METHOD_PATH = CONFIG_DIR / "scoring_method.yaml"

Confidence = Literal["high", "medium", "low"]
BaseKind = Literal["events", "events_only_if_found", "never", "index:credit_rating", "index:wgi_political_stability",
                   "index:inform_human_hazard", "index:inform_natural_hazard", "index_or_events:altman",
                   "index_or_events:injury_rate", "index_or_events:esg", "index_or_events:security_rating"]


# ---------------------------------------------------------------------------
# Level bands and rounding
# ---------------------------------------------------------------------------


def level_for(score: int | None, levels: list[tuple[ScoreLevel, int]] | None = None) -> ScoreLevel | None:
    """Level band for a 0-100 score: Low 0-24, Medium 25-49, High 50-74, Critical 75-100."""
    if score is None:
        return None
    bands = sorted(levels or DEFAULT_LEVELS, key=lambda b: b[1])
    name: ScoreLevel | None = None
    for band, low in bands:
        if score >= low:
            name = band
    return name


def round_half_even(x: float) -> int:
    """Round like the dataset's Total_Risk_Index (half to even), immune to binary float noise."""
    return int(Decimal(repr(round(x, 9))).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def _r(x: float, nd: int = 2) -> float:
    """Stable rounding for stored numbers, so JSON output is byte-identical across runs."""
    return float(Decimal(repr(round(x, 9))).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_EVEN))


def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def coverage_for(status: AreaStatus | None) -> Coverage:
    """Coverage counts only pages that gave a verified fact for the area, not pages merely read."""
    if status is None:
        return "not_assessed"
    if status.trusted_pages_used > 0:
        return "assessed"
    return "unverified_only" if status.unverified_pages_used > 0 else "not_assessed"


# ---------------------------------------------------------------------------
# Method config (config/scoring_method.yaml)
# ---------------------------------------------------------------------------


class _C(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Anchors(_C):
    nothing_adverse: float = Field(ge=0, lt=100)
    fresh_red_event: float = Field(gt=0, lt=100)
    fresh_amber_event: float = Field(gt=0, lt=100)


class RecencyMethod(_C):
    drop_after_stale_multiple: float = Field(gt=1)
    sentiment_stale_years: float = Field(gt=0)
    sentiment_scores: list[str]


class UnverifiedMethod(_C):
    credibility_2_weight: float = Field(gt=0, le=1)
    credibility_3_weight: float = Field(gt=0, le=1)
    credibility_2_range: tuple[float, float]
    credibility_3_range: tuple[float, float]
    official_domain_suffixes: list[str]
    on_record_attributions: list[str]


class Licensed(_C):
    msci: bool = False
    sustainalytics: bool = False
    securityscorecard: bool = False


class TotalMethod(_C):
    unverified_only_counts_toward_coverage: bool = True


class SeverityMethod(_C):
    low_fine_share_of_revenue: float = Field(gt=0, lt=1)
    fine_event_types: list[str]


class SafetyMethod(_C):
    doubling_counts_as: Literal["red", "amber"]


class CreditMethod(_C):
    pd3_percent: dict[str, float]
    moodys_to_sp: dict[str, str]
    sp_aliases: dict[str, str]


class AltmanMethod(_C):
    intercept: float
    coefficients: dict[str, float]
    rating_medians_2013: dict[str, float]
    max_accounts_age_years: int


class EsgMethod(_C):
    sustainalytics_knots: list[tuple[float, float]]
    msci_letters: dict[str, float]


class SubScoreMethod(_C):
    weight: float = Field(gt=0, le=1)
    base: BaseKind
    events: list[str] | Literal["all_adverse", "reputation_area"]
    knockout_events: list[str] = Field(default_factory=list)


class OverrideMethod(_C):
    """Override rules (scoring_method.yaml ``overrides``; appendix §A5)."""

    trusted_red_area_floor: float = Field(default=50, ge=0, le=100)
    knockout_total_floor: float = Field(default=75, ge=0, le=100)


class MethodConfig(_C):
    version: int
    anchors: Anchors
    recency: RecencyMethod
    unverified: UnverifiedMethod
    licensed: Licensed
    country_basis: Literal["sites_then_hq", "hq_only", "sites_only"]
    total: TotalMethod
    overrides: OverrideMethod = Field(default_factory=OverrideMethod)
    severity: SeverityMethod
    safety: SafetyMethod
    credit: CreditMethod
    altman: AltmanMethod
    esg: EsgMethod
    country_data_indicators: dict[str, Literal["wgi_political_stability", "inform_human_hazard",
                                                "inform_natural_hazard"]]
    sub_scores: dict[str, SubScoreMethod]

    @field_validator("sub_scores")
    @classmethod
    def _events_known(cls, v: dict[str, SubScoreMethod]) -> dict[str, SubScoreMethod]:
        for name, m in v.items():
            names = m.events if isinstance(m.events, list) else []
            unknown = sorted(set(names + m.knockout_events) - set(EVENT_TYPES))
            if unknown:
                raise ValueError(f"{name}: unknown event types {unknown}")
        return v


def load_method(path: Path | None = None, scoring: ScoringConfig | None = None) -> MethodConfig:
    """Load scoring_method.yaml and check it against scoring.yaml (same 18 columns, weights sum
    per area to the area weight)."""
    p = path or METHOD_PATH
    if not p.exists():
        raise ConfigError(f"missing config file: {p}")
    data: Any = yaml.safe_load(p.read_text(encoding="utf-8"))
    try:
        m = MethodConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"{p.name} invalid: {exc}") from exc
    if scoring is not None:
        mapped = {c for a in scoring.areas.values() for c in a.sub_scores}
        if mapped != set(m.sub_scores):
            raise ConfigError(f"{p.name}: sub_scores must match scoring.yaml; differ by {sorted(mapped ^ set(m.sub_scores))}")
        for area, amap in scoring.areas.items():
            w = sum(m.sub_scores[c].weight for c in amap.sub_scores)
            if abs(w - amap.weight) > 1e-6:
                raise ConfigError(f"{p.name}: sub-score weights for {area} sum to {w:.3f}, scoring.yaml says {amap.weight}")
    return m


OVERRIDE_PRECEDENT = (
    "precedent: S&P Global Ratings lets one decisive factor override or cap the weighted result: the "
    "'overriding factors' step of 'Methodology For Rating Local And Regional Governments Outside Of The U.S.' "
    "(15 July 2019; https://www.maalot.co.il/Publications/MT20200715130530.PDF) and the caps in "
    "'How We Rate Insurers' (https://www.spglobal.com/content/dam/spglobal/ratings/en/documents/pdfs/"
    "how-we-rate-insurers.pdf)")


@dataclass(frozen=True)
class Derived:
    """Constants computed from the anchors and the level bands (appendix §A3, §A5)."""

    base: float
    p_red: float
    p_amber: float
    halflife_factor: float
    band_width: float
    unverified_cap: float
    min_coverage: float
    safety_slope: float

    def as_dict(self) -> dict[str, float]:
        return {k: _r(v, 4) for k, v in self.__dict__.items()}


def _points_for(anchor: float, base: float) -> float:
    """Points one fresh trusted event needs so that, from ``base``, the score lands on ``anchor``."""
    return 100.0 * (1.0 - (100.0 - anchor) / (100.0 - base))


def derive(m: MethodConfig, levels: Sequence[tuple[ScoreLevel, int]]) -> Derived:
    a = m.anchors
    if not a.nothing_adverse < a.fresh_amber_event < a.fresh_red_event:
        raise ConfigError("anchors must satisfy nothing_adverse < fresh_amber_event < fresh_red_event")
    p_red, p_amber = _points_for(a.fresh_red_event, a.nothing_adverse), _points_for(a.fresh_amber_event, a.nothing_adverse)
    mins = sorted(b for _, b in levels)
    band = float(min(y - x for x, y in zip(mins, mins[1:]))) if len(mins) > 1 else 25.0
    doubling = a.fresh_amber_event if m.safety.doubling_counts_as == "amber" else a.fresh_red_event
    return Derived(base=a.nothing_adverse, p_red=p_red, p_amber=p_amber,
                   halflife_factor=math.log(2) / math.log(p_red / p_amber), band_width=band,
                   unverified_cap=band, min_coverage=1.0 - 2.0 * band / 100.0,
                   safety_slope=doubling - a.nothing_adverse)


# ---------------------------------------------------------------------------
# Breakdown types ("How was this scored?")
# ---------------------------------------------------------------------------


class Contribution(BaseModel):
    """One line of the breakdown: what went in, how much it counted, and why."""

    kind: Literal["base", "event", "not_counted", "override", "cap", "input_not_used"]
    ref: str = Field(description="Flag id, or input name such as 'credit_rating:S&P'.")
    label: str
    points: float | None = Field(default=None, description="Event points p (0-100) or base score.")
    rule: str = Field(description="Rule name and its source, e.g. 'anchor: fresh red event = 50 (appendix §A3)'.")
    source: str = Field(default="", description="Source ids or URL behind this line.")


class SubScoreDetail(BaseModel):
    name: str
    area: UmbrellaId
    weight: float
    score: int | None
    level: ScoreLevel | None
    confidence: Confidence | None
    includes_unverified: bool = False
    unverified_only: bool = False
    not_assessed_reason: str = ""
    formula: str = ""
    contributions: list[Contribution] = Field(default_factory=list)


class AreaDetail(BaseModel):
    area: UmbrellaId
    label: str
    score: int | None
    level: ScoreLevel | None
    weight: float
    coverage_fraction: float
    formula: str
    sub_scores: list[SubScoreDetail]
    contributions: list[Contribution] = Field(default_factory=list, description="Area-level overrides.")


class ScoringReport(BaseModel):
    as_of: str
    total: int | None
    total_level: ScoreLevel | None
    total_shown: bool
    total_formula: str
    coverage: float
    coverage_unverified_only: float
    range_low: int | None
    range_high: int | None
    knockout: bool
    total_contributions: list[Contribution] = Field(default_factory=list, description="Total-level overrides.")
    confidence_shares: dict[str, float]
    areas: list[AreaDetail]
    constants: dict[str, float]
    decisions: dict[str, str]
    card: ScoreCard


# ---------------------------------------------------------------------------
# Index-based bases (appendix §A2)
# ---------------------------------------------------------------------------


def _credit_scale(m: CreditMethod) -> dict[str, float]:
    """Score per Table 26 bucket: log scale between the AAA rate (0) and default (100), monotone."""
    floor = m.pd3_percent["AAA"]
    lo, hi = math.log10(floor), math.log10(100.0)
    out: dict[str, float] = {}
    running = 0.0
    for bucket, pd in m.pd3_percent.items():
        running = max(running, pd, floor)
        out[bucket] = 100.0 * (math.log10(running) - lo) / (hi - lo)
    return out


def _sp_bucket(r: CreditRatingInput, m: CreditMethod) -> str | None:
    raw = r.rating.strip()
    if r.agency == "Moody's":
        return m.moodys_to_sp.get(raw)
    sym = raw.upper()
    sym = m.sp_aliases.get(sym, sym)
    return sym if sym in m.pd3_percent else None


def _combine_ratings(scores: list[float]) -> float:
    """CRR Art. 138(e)-(f): one -> it; two -> the worse; three or more -> the worse of the two best.
    With scores sorted best (lowest) first, both multi-rating cases pick the second value."""
    s = sorted(scores)
    return s[0] if len(s) == 1 else s[1]


def _altman_z(m: AltmanMethod, a: AltmanInputs) -> float:
    c = m.coefficients
    return (m.intercept
            + c["working_capital_to_assets"] * (a.current_assets - a.current_liabilities) / a.total_assets
            + c["retained_earnings_to_assets"] * a.retained_earnings / a.total_assets
            + c["ebit_to_assets"] * a.ebit / a.total_assets
            + c["book_equity_to_liabilities"] * a.book_equity / a.total_liabilities)


def _altman_bucket(z: float, m: AltmanMethod) -> str:
    """Nearest 2013 median; ties go to the worse rating (later in the list)."""
    best, best_d = "", math.inf
    for bucket, med in m.rating_medians_2013.items():
        d = abs(z - med)
        if d <= best_d:
            best, best_d = bucket, d
    return best


def _piecewise(x: float, knots: list[tuple[float, float]]) -> float:
    if x <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:]):
        if x1 > x0 and x0 <= x < x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return min(100.0, knots[-1][1])


def _ev(e: Evidence) -> str:
    return e.source_id or e.source_url


@dataclass
class _Base:
    value: float
    label: str
    rule: str
    source: str
    confidence: Confidence


def _country_base(kind: str, inputs: ScoringInputs, m: MethodConfig, notes: list[Contribution]) -> _Base | None:
    index = kind.split(":", 1)[1]
    rows = [c for c in inputs.country_indices if c.index == index]
    for c in rows:
        if c.evidence.trust != "trusted":
            notes.append(Contribution(kind="input_not_used", ref=f"{index}:{c.country_code}", label=f"{c.value} ({c.year})",
                                      rule="numeric inputs from unverified sources are not used", source=_ev(c.evidence)))
    rows = [c for c in rows if c.evidence.trust == "trusted"]
    sites = [c for c in rows if c.basis == "site"]
    hq = [c for c in rows if c.basis == "hq"]
    if m.country_basis == "hq_only":
        use, basis = hq, "HQ country"
    elif m.country_basis == "sites_only":
        use, basis = sites, "supplying sites"
    else:
        use, basis = (sites, "supplying sites") if sites else (hq, "HQ country")
    if not use:
        return None

    def conv(c: CountryIndexInput) -> float:
        return 100.0 - c.value if index == "wgi_political_stability" else 10.0 * c.value

    total_share = sum(c.share for c in use)
    value = sum(conv(c) * c.share for c in use) / total_share
    label = ", ".join(f"{c.country_code} {c.value:g} ({c.year})" for c in sorted(use, key=lambda c: c.country_code))
    rule = ("100 - WGI Political Stability score (WGI 2025, appendix §A2)" if index == "wgi_political_stability"
            else f"10 x INFORM {'human' if 'human' in index else 'natural'} hazard category (INFORM 2017, appendix §A2)")
    return _Base(value=_clamp(value), label=f"{basis}: {label}", rule=f"{rule}; basis = {basis} (Decision 3)",
                 source="; ".join(_ev(c.evidence) for c in sorted(use, key=lambda c: c.country_code)), confidence="high")


def _index_base(kind: str, inputs: ScoringInputs | None, m: MethodConfig, d: Derived, as_of: date,
                notes: list[Contribution]) -> _Base | None:
    if inputs is None:
        return None
    if kind.startswith("index:") and kind != "index:credit_rating":
        return _country_base(kind, inputs, m, notes)
    if kind == "index:credit_rating":
        scale = _credit_scale(m.credit)
        scored: list[tuple[float, CreditRatingInput, str]] = []
        for r in inputs.credit_ratings:
            if r.evidence.trust != "trusted":
                notes.append(Contribution(kind="input_not_used", ref=f"credit_rating:{r.agency}", label=r.rating,
                                          rule="numeric inputs from unverified sources are not used", source=_ev(r.evidence)))
                continue
            b = _sp_bucket(r, m.credit)
            if b is None:
                notes.append(Contribution(kind="input_not_used", ref=f"credit_rating:{r.agency}", label=r.rating,
                                          rule="rating symbol not recognised", source=_ev(r.evidence)))
                continue
            scored.append((scale[b], r, b))
        if not scored:
            return None
        value = _combine_ratings([s for s, _, _ in scored])
        parts = ", ".join(f"{r.agency} {r.rating} -> {b} ({_r(s, 1)})" for s, r, b in sorted(scored, key=lambda t: t[1].agency))
        outlooks = "; ".join(f"{r.agency} outlook {r.outlook}" for _, r, _ in scored if r.outlook)
        rule = ("S&P 3-year default rate on a log scale (S&P 2024 study T26; EU 2016/1799); "
                "several ratings combined by CRR Art. 138" + (f"; {outlooks} (shown, not scored)" if outlooks else ""))
        return _Base(value=value, label=parts, rule=rule,
                     source="; ".join(_ev(r.evidence) for _, r, _ in sorted(scored, key=lambda t: t[1].agency)),
                     confidence="high")
    if kind == "index_or_events:altman" and inputs.altman is not None:
        a = inputs.altman
        if a.evidence.trust != "trusted":
            notes.append(Contribution(kind="input_not_used", ref="altman", label=a.fiscal_year_end,
                                      rule="numeric inputs from unverified sources are not used", source=_ev(a.evidence)))
            return None
        z = _altman_z(m.altman, a)
        b = _altman_bucket(z, m.altman)
        fy = parse_event_date(a.fiscal_year_end)
        fresh = fy is not None and (as_of.year - fy.year) <= m.altman.max_accounts_age_years
        return _Base(value=_credit_scale(m.credit)[b], label=f"Z'' = {_r(z)} -> {b} (FY {a.fiscal_year_end})",
                     rule="Altman Z'' -> nearest 2013 rating median -> credit scale (appendix §A2)",
                     source=_ev(a.evidence), confidence="high" if fresh else "medium")
    if kind == "index_or_events:injury_rate" and inputs.injury_rate is not None:
        ir = inputs.injury_rate
        if ir.evidence.trust != "trusted" or ir.benchmark_evidence.trust != "trusted":
            notes.append(Contribution(kind="input_not_used", ref="injury_rate", label=f"{ir.metric} {ir.company_rate}",
                                      rule="numeric inputs from unverified sources are not used", source=_ev(ir.evidence)))
            return None
        ratio = ir.company_rate / ir.benchmark_rate
        value = _clamp(d.base + d.safety_slope * math.log2(ratio))
        return _Base(value=value, label=f"{ir.metric} {ir.company_rate:g} vs {ir.benchmark_label} {ir.benchmark_rate:g} "
                                         f"(ratio {_r(ratio)})",
                     rule=f"base {d.base:g} + {d.safety_slope:g} x log2(ratio): industry average = nothing adverse, "
                          f"2x = one {m.safety.doubling_counts_as} event (calibration parameter, appendix §A6)",
                     source=f"{_ev(ir.evidence)}; {_ev(ir.benchmark_evidence)}", confidence="medium")
    if kind == "index_or_events:esg":
        if inputs.ecovadis is not None and inputs.ecovadis.evidence.trust != "trusted":
            notes.append(Contribution(kind="input_not_used", ref="esg:ecovadis", label=f"{inputs.ecovadis.score:g}",
                                      rule="numeric inputs from unverified sources are not used",
                                      source=_ev(inputs.ecovadis.evidence)))
        if inputs.ecovadis is not None and inputs.ecovadis.evidence.trust == "trusted":
            e = inputs.ecovadis
            return _Base(value=_clamp(100.0 - e.score), label=f"EcoVadis {e.score:g}/100",
                         rule="100 - EcoVadis score (EcoVadis 2026 methodology, appendix §A2)", source=_ev(e.evidence),
                         confidence="high")
        for le in sorted(inputs.licensed_esg, key=lambda x: x.provider):
            if le.evidence.trust != "trusted":
                continue
            if le.provider == "sustainalytics" and m.licensed.sustainalytics:
                try:
                    v = float(le.value)
                except ValueError:
                    continue
                return _Base(value=_clamp(_piecewise(v, m.esg.sustainalytics_knots)), label=f"Sustainalytics {v:g}",
                             rule="Sustainalytics band-to-band mapping (licensed; appendix §A2)", source=_ev(le.evidence),
                             confidence="high")
            if le.provider == "msci" and m.licensed.msci and le.value.upper() in m.esg.msci_letters:
                return _Base(value=m.esg.msci_letters[le.value.upper()], label=f"MSCI {le.value.upper()}",
                             rule="MSCI letter, even split inside MSCI groups (licensed; appendix §A2)",
                             source=_ev(le.evidence), confidence="high")
            notes.append(Contribution(kind="input_not_used", ref=f"esg:{le.provider}", label=le.value,
                                      rule="no licence for this provider (Decision 2)", source=_ev(le.evidence)))
        return None
    if kind == "index_or_events:security_rating" and inputs.security_rating is not None:
        sr = inputs.security_rating
        if not m.licensed.securityscorecard or sr.evidence.trust != "trusted":
            notes.append(Contribution(kind="input_not_used", ref="security_rating", label=f"{sr.score:g}",
                                      rule="no licence for SecurityScorecard (Decision 2)" if not m.licensed.securityscorecard
                                      else "numeric inputs from unverified sources are not used", source=_ev(sr.evidence)))
            return None
        return _Base(value=_clamp(100.0 - sr.score), label=f"SecurityScorecard {sr.score:g}",
                     rule="100 - SecurityScorecard score (licensed)", source=_ev(sr.evidence), confidence="high")
    return None


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@dataclass
class _Ev:
    flag: Flag
    colour: Literal["red", "amber"]
    colour_note: str
    weight: float           # source weight S
    weight_note: str
    counted_as_trusted: bool
    knockout_ok: bool
    blocked_knockout: bool


def _is_official(url: str, suffixes: list[str]) -> bool:
    host = domain_of(url)
    return any(host.endswith(s) or host == s.lstrip(".") for s in suffixes)


def _source_weight(f: Flag, m: MethodConfig, inputs: ScoringInputs | None,
                   sources: Mapping[str, Source]) -> tuple[float, str, bool]:
    """Source weight S, reason, and whether the fact counts as trusted (appendix §A3, §A4)."""
    ids = ", ".join(f.source_ids)
    if f.trust == "trusted":
        if f.company_stated:
            return 1.0, f"company-stated adverse fact: statement against interest, FRE 804(b)(3) [{ids}]", True
        return 1.0, f"trusted source on the allowlist [{ids}]", True
    s = f.signals
    if s.corroborated_by_trusted:
        return 1.0, f"unverified, but confirmed by a trusted source: Admiralty credibility 1 [{ids}]", True
    u = m.unverified
    failed: list[str] = []
    if s.attribution not in u.on_record_attributions:
        failed.append(f"E1 not on the record ({s.attribution})")
    if f.claim_status == "unclear":
        failed.append("E2 not a clear factual claim")
    if not s.publisher_named:
        failed.append("E3 no accountable publisher")
    if not s.dated:
        failed.append("E4 undated")
    if not s.claim_specific_checkable:
        failed.append("E5 not specific/checkable")
    if failed:
        return 0.0, f"unverified, fails the eligibility gate: {'; '.join(failed)} (appendix §A4) [{ids}]", False
    primary = f.source_ids[0] if f.source_ids else ""
    src = sources.get(primary)
    if src is not None and _is_official(src.url, u.official_domain_suffixes):
        grade = "B"
    else:
        grade = (inputs.source_reliability.get(primary, "D") if inputs else "D")
    if grade == "D":
        if not s.cites_primary_document:
            return 0.0, f"unverified, reliability D without a primary document: ineligible (appendix §A4) [{ids}]", False
        cred = 3
    else:
        cred = 2 if (s.cites_primary_document or s.independent_domains >= 2) else 3
    w = u.credibility_2_weight if cred == 2 else u.credibility_3_weight
    phia = "probably true (PHIA >= 55 %)" if cred == 2 else "possibly true (PHIA >= 40 %)"
    return w, f"unverified, Admiralty {grade}{cred} = {phia}, weight {w:g} (JDP 2-00; appendix §A4) [{ids}]", False


def _event_colour(f: Flag, rules: Rules, m: MethodConfig, inputs: ScoringInputs | None) -> tuple[Colour, str]:
    """Colour before staleness and before the unverified cap: those two are handled by decay and
    by the source weight here, so they must not be counted twice."""
    rule = rules.event_types[f.event_type]
    colour: Colour = rule.colour
    low = f.severity == "low"
    note = f"{f.event_type} -> {colour} (rules.yaml)"
    if f.event_type in m.severity.fine_event_types and inputs is not None:
        fine = next((x for x in inputs.fines if x.flag_id == f.id and x.evidence.trust == "trusted"), None)
        if fine is not None:
            share = fine.amount / fine.revenue
            low = share < m.severity.low_fine_share_of_revenue
            note += (f"; amount {_r(share * 100, 3)} % of revenue -> {'low' if low else 'not low'} severity "
                     f"(threshold {m.severity.low_fine_share_of_revenue * 100:g} %, calibration parameter §A6)")
    if low and colour == "red":
        colour = "amber"
        note += "; low severity -> amber (rules.yaml)"
    return colour, note


def _stale_years(event_type: str, sub: str, rules: Rules, m: MethodConfig, default_years: int) -> float | None:
    if sub in m.recency.sentiment_scores:
        return m.recency.sentiment_stale_years
    w = rules.event_types[event_type].stale_after_years
    if w == "never":
        return None
    return float(default_years if w is None else w)


def _age_years(f: Flag, as_of: date) -> tuple[float, str]:
    d = parse_event_date(f.event_date)
    if d is None:
        return 0.0, "date unknown, treated as current"
    return max(0.0, (as_of - d).days / 365.25), f"event {f.event_date}"


def _combine(base: float, ps: Sequence[float]) -> float:
    rest = 100.0 - base
    for p in ps:
        rest *= 1.0 - p / 100.0
    return _clamp(100.0 - rest)


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------


@dataclass
class _Run:
    m: MethodConfig
    d: Derived
    rules: Rules
    as_of: date
    default_years: int
    inputs: ScoringInputs | None
    sources: Mapping[str, Source]
    levels: list[tuple[ScoreLevel, int]]


def _targets(f: Flag, sub: str, sm: SubScoreMethod) -> bool:
    if sm.events == "all_adverse":
        return True
    if sm.events == "reputation_area":
        return f.area == "reputation"
    return f.event_type in sm.events or f.event_type in sm.knockout_events


def _month_key(f: Flag) -> str:
    d = parse_event_date(f.event_date)
    return f"{f.event_type}|{d.year:04d}-{d.month:02d}" if d else f"{f.event_type}|undated|{f.id}"


CONTEXT_BASE_LABEL = ("checked: only older, resolved or neutral facts found, nothing current and adverse "
                      "(appendix §A3)")


def _pipeline_not_assessed(run: _Run, sub: str, area: UmbrellaId) -> SubScoreDetail:
    sm = run.m.sub_scores[sub]
    return SubScoreDetail(name=sub, area=area, weight=sm.weight, score=None, level=None, confidence=None,
                          not_assessed_reason="the research pipeline found no trusted evidence for this area, "
                                              "so nothing in it is scored (never 0)")


def _score_sub(run: _Run, sub: str, area: UmbrellaId, area_has_evidence: bool, area_unverified_only: bool,
               flags: Sequence[Flag], context_area: bool = False) -> SubScoreDetail:
    m, d = run.m, run.d
    sm = m.sub_scores[sub]
    detail = SubScoreDetail(name=sub, area=area, weight=sm.weight, score=None, level=None, confidence=None)
    if sm.base == "never":
        detail.not_assessed_reason = "no public method for this score (appendix §A2): Not assessed, never 0"
        return detail

    notes: list[Contribution] = []
    base = _index_base(sm.base, run.inputs, m, d, run.as_of, notes) if sm.base != "events" else None

    # Events that target this sub-score.
    evs: list[_Ev] = []
    for f in sorted(flags, key=lambda x: x.id):
        if not _targets(f, sub, sm):
            continue
        colour, cnote = _event_colour(f, run.rules, m, run.inputs)
        if colour not in ("red", "amber"):
            continue  # positives and neutral context are shown in the report, not scored (appendix §A3)
        w, wnote, trusted_like = _source_weight(f, m, run.inputs, run.sources)
        is_ko = f.event_type in sm.knockout_events and bool(run.rules.event_types[f.event_type].knockout)
        ko_ok = is_ko and trusted_like and colour == "red"
        blocked = is_ko and not trusted_like
        if blocked:
            w, wnote = 0.0, wnote + "; unconfirmed knock-out lead: never a knock-out from unverified sources, " \
                                    "check the official register"
        evs.append(_Ev(flag=f, colour="red" if colour == "red" else "amber", colour_note=cnote, weight=w,
                       weight_note=wnote, counted_as_trusted=trusted_like, knockout_ok=ko_ok, blocked_knockout=blocked))

    # Points, decay, dedupe (same event type and month -> counted once, highest points).
    scored: list[tuple[float, _Ev, str]] = []
    for e in evs:
        p_col = d.p_red if e.colour == "red" else d.p_amber
        age, age_note = _age_years(e.flag, run.as_of)
        stale = _stale_years(e.flag.event_type, sub, run.rules, m, run.default_years)
        if stale is None:
            decay, dnote = 1.0, f"{age_note}; never goes stale"
        elif age > m.recency.drop_after_stale_multiple * stale:
            decay, dnote = 0.0, f"{age_note}; older than {m.recency.drop_after_stale_multiple:g} x {stale:g} y: dropped"
        else:
            h = d.halflife_factor * stale
            decay = 0.5 ** (age / h)
            dnote = f"{age_note}; decay 0.5^({_r(age)}/{_r(h)}) = {_r(decay, 3)}"
        p = p_col * decay * e.weight
        why = (f"{e.colour} event: P = {_r(p_col)} (anchor: fresh {e.colour} = "
               f"{m.anchors.fresh_red_event if e.colour == 'red' else m.anchors.fresh_amber_event:g}); {dnote}; "
               f"source weight {e.weight:g}: {e.weight_note}; {e.colour_note}")
        scored.append((p, e, why))

    best: dict[str, tuple[float, _Ev, str]] = {}
    for p, e, why in scored:
        k = _month_key(e.flag)
        if k not in best or p > best[k][0]:
            best[k] = (p, e, why)
    counted_ids = {v[1].flag.id for v in best.values()}

    for p, e, why in scored:
        if e.flag.id not in counted_ids:
            keep = best[_month_key(e.flag)][1].flag.id
            notes.append(Contribution(kind="not_counted", ref=e.flag.id, label=e.flag.summary, points=_r(p),
                                      rule=f"same event as {keep} (same type and month): counted once, highest points",
                                      source=", ".join(e.flag.source_ids)))
    counted = [(p, e, why) for p, e, why in scored if e.flag.id in counted_ids]
    trusted_ps = [p for p, e, _ in counted if e.counted_as_trusted and p > 0]
    unv_ps = [p for p, e, _ in counted if not e.counted_as_trusted and p > 0]

    # Assessed?
    has_counted = bool(trusted_ps or unv_ps)
    ko = any(e.knockout_ok for _, e, _ in counted)
    if sm.base.startswith("index:"):
        assessed = base is not None or ko
    elif sm.base == "events_only_if_found":
        assessed = has_counted
    else:
        assessed = base is not None or has_counted or area_has_evidence
    if area_unverified_only and base is None and not trusted_ps and not m.total.unverified_only_counts_toward_coverage:
        assessed = False

    if not assessed:
        detail.not_assessed_reason = (
            "no input value for this index score" if sm.base.startswith("index:")
            else "no verified fact for this area or score")
        detail.contributions = notes
        return detail

    if base is None:
        b = _Base(value=d.base, label=(CONTEXT_BASE_LABEL if context_area else "nothing adverse found in the sources checked")
                  if not has_counted else "default base",
                  rule=f"anchor: nothing adverse = {d.base:g}, middle of the Low band (appendix §A3)", source="",
                  confidence="low")
    else:
        b = base
    contribs: list[Contribution] = [Contribution(kind="base", ref=sm.base, label=b.label, points=_r(b.value),
                                                 rule=b.rule, source=b.source)]
    for p, e, why in counted:
        kind: Literal["event", "not_counted"] = "event" if p > 0 else "not_counted"
        contribs.append(Contribution(kind=kind, ref=e.flag.id, label=e.flag.summary, points=_r(p), rule=why,
                                     source=", ".join(e.flag.source_ids)))
    contribs += notes

    s_trusted = _combine(b.value, trusted_ps)
    s_all = _combine(b.value, trusted_ps + unv_ps)
    value = s_all
    if s_all > s_trusted + d.unverified_cap:
        value = s_trusted + d.unverified_cap
        contribs.append(Contribution(kind="cap", ref="unverified_cap", label=f"{_r(s_all)} capped to {_r(value)}",
                                     points=_r(d.unverified_cap),
                                     rule=f"unverified-only events add at most one Level band ({d.unverified_cap:g} points; "
                                          "appendix §A4 guard 2)"))
    if ko:
        value = 100.0
        ko_ids = ", ".join(e.flag.id for _, e, _ in counted if e.knockout_ok)
        contribs.append(Contribution(kind="override", ref=ko_ids, label="knock-out", points=100.0,
                                     rule="trusted knock-out (rules.yaml): score 100; default = probability of default 100 %"))

    detail.score = round_half_even(value)
    detail.level = level_for(detail.score, run.levels)
    detail.includes_unverified = bool(unv_ps)
    detail.unverified_only = area_unverified_only and base is None and not trusted_ps
    if ko or b.confidence == "high":
        conf: Confidence = "high"
    elif trusted_ps or b.confidence == "medium" or any(
            e.counted_as_trusted and e.flag.signals.independent_domains >= 2 for _, e, _ in counted):
        conf = "medium"
    else:
        conf = "low"
    if detail.includes_unverified or detail.unverified_only:
        conf = "low"
    detail.confidence = conf
    detail.formula = (f"score = 100 - (100 - base {_r(b.value)}) x product(1 - p/100) over {len(trusted_ps) + len(unv_ps)} "
                      f"counted event(s) = {_r(value)} -> {detail.score}")
    detail.contributions = contribs
    return detail


def _area_formula(subs: list[SubScoreDetail]) -> tuple[int | None, float, str]:
    got = [s for s in subs if s.score is not None]
    wt = sum(s.weight for s in subs)
    if not got:
        return None, 0.0, "Not assessed: no sub-score has evidence (never 0)"
    w = sum(s.weight for s in got)
    val = sum(s.weight * (s.score or 0) for s in got) / w
    names = ", ".join(f"{s.name.replace('_Score', '')} {s.score} x {s.weight:g}" for s in got)
    return round_half_even(val), w / wt, f"weighted mean of {len(got)} of {len(subs)} sub-scores ({names}) / {_r(w)}"


_WGI_PV = "GOV_WGI_PV.SC"


def _figures(data: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not data:
        return []
    figs = data.get("figures")
    if isinstance(figs, list):
        return [f for f in figs if isinstance(f, Mapping)]
    return [data] if "indicator" in data else []


def inputs_from_flag_data(flags: Sequence[Flag], inputs: ScoringInputs | None,
                          indicator_map: Mapping[str, CountryIndex]) -> ScoringInputs | None:
    """Add country figures carried in ``Flag.data`` (research_agent/country_data.py) to the
    country inputs. Explicit inputs for the same index, country and basis win."""
    base = inputs or ScoringInputs()
    have: set[tuple[str, str, str]] = {(c.index, c.country_code, c.basis) for c in base.country_indices}
    extra: list[CountryIndexInput] = []
    for f in sorted(flags, key=lambda x: x.id):
        for fig in _figures(f.data):
            index = indicator_map.get(str(fig.get("indicator", "")))
            url = str(fig.get("source_url", ""))
            m = re.search(r"/country/([A-Za-z]{2})/", url)
            code = str(fig.get("country_code") or (m.group(1) if m else "")).upper()
            if index is None or len(code) != 2 or not url or fig.get("value") is None or fig.get("year") is None:
                continue
            key = (index, code, "hq")
            if key in have:
                continue
            have.add(key)
            ev = Evidence(source_url=url, quote=f.quote or f"value {fig['value']}", date=str(fig["year"]),
                          trust=f.trust, source_id=f.source_ids[0] if f.source_ids else None)
            extra.append(CountryIndexInput(index=index, country_code=code,
                                           value=float(fig["value"]), year=int(fig["year"]), basis="hq", evidence=ev))
    if not extra:
        return inputs
    return base.model_copy(update={"country_indices": base.country_indices + tuple(extra)})


def _area_has_eligible(area: UmbrellaId, flags: Sequence[Flag], run: _Run) -> bool:
    """An unverified-only area counts as having evidence only if one of its facts passes the
    eligibility gate (appendix §A4): hearsay alone never makes an area "assessed"."""
    return any(_source_weight(f, run.m, run.inputs, run.sources)[0] > 0 for f in flags if f.area == area)


def _current_trusted_reds(area: UmbrellaId, flags: Sequence[Flag], run: _Run) -> list[Flag]:
    """Trusted red facts of ``area`` that are still current (not past their staleness date).
    Unverified-only facts never count here, so they can never trigger the area floor."""
    out: list[Flag] = []
    for f in sorted(flags, key=lambda x: x.id):
        if f.area != area:
            continue
        colour, _ = _event_colour(f, run.rules, run.m, run.inputs)
        if colour != "red" or not _source_weight(f, run.m, run.inputs, run.sources)[2]:
            continue
        stale = _stale_years(f.event_type, "", run.rules, run.m, run.default_years)
        if stale is not None and _age_years(f, run.as_of)[0] > stale:
            continue
        out.append(f)
    return out


def _area_floor(area: UmbrellaId, score: int | None, flags: Sequence[Flag], run: _Run,
                ov: OverrideMethod) -> tuple[int | None, list[Contribution]]:
    """Override 1: a current trusted red fact puts its area at least at the floor (start of High)."""
    if score is None:
        return None, []
    reds = _current_trusted_reds(area, flags, run)
    floor = round_half_even(ov.trusted_red_area_floor)
    if not reds or score >= floor:
        return score, []
    ids = ", ".join(f.id for f in reds)
    return floor, [Contribution(
        kind="override", ref=ids, label=f"area floor: {score} raised to {floor}", points=float(floor),
        rule=(f"a current, trusted red fact puts its area at least at {floor} (High); unverified-only facts "
              f"never do (scoring_method.yaml overrides; appendix §A5); {OVERRIDE_PRECEDENT}"),
        source=", ".join(sorted({s for f in reds for s in f.source_ids})))]


def _default_years() -> int:
    try:
        return load_settings().recency.default_years
    except (ConfigError, OSError, ValueError):
        return 3


def score_detailed(flags: list[Flag], areas: list[AreaStatus], cfg: ScoringConfig | None = None, *,
                   inputs: ScoringInputs | None = None, rules: Rules | None = None, as_of: date | None = None,
                   sources: Sequence[Source] | None = None, method: MethodConfig | None = None,
                   default_years: int | None = None, labels: Mapping[str, str] | None = None) -> ScoringReport:
    """Score every sub-score, area and the total, with a full per-fact breakdown."""
    cfg = cfg or load_scoring()
    m = method or load_method(scoring=cfg)
    levels: list[tuple[ScoreLevel, int]] = [(b.name, b.min) for b in cfg.levels]
    d = derive(m, levels)
    inputs = inputs_from_flag_data(flags, inputs, m.country_data_indicators)
    run = _Run(m=m, d=d, rules=rules or load_rules(), as_of=as_of or date.today(),
               default_years=default_years if default_years is not None else _default_years(),
               inputs=inputs, sources={s.id: s for s in (sources or [])}, levels=levels)
    ov = m.overrides
    status_by_area = {a.area: a for a in areas}
    label_of: dict[str, str] = {a.area: a.label for a in areas}
    label_of.update(labels or {})

    area_details: list[AreaDetail] = []
    card_areas: list[AreaScore] = []
    for area in UMBRELLAS:
        st = status_by_area.get(area)
        cov = coverage_for(st)
        # The pipeline's area status wins: "not_assessed" -> nothing in the area is scored.
        # "context" (only neutral, older or resolved facts) is scored like any area with a
        # verified fact (appendix §A3: "a score is produced only if its area has >= 1 verified
        # fact"): base 12, and older events count with their decay until the drop age
        # (2 x stale_after_years). So a settled 2018 case is "checked, resolved": evidence, not a
        # red flag. Before, such areas were Not assessed, which hid areas that were checked.
        if st is None or st.status == "not_assessed" or cov == "not_assessed":
            subs = [_pipeline_not_assessed(run, c, area) for c in cfg.areas[area].sub_scores]
        else:
            has_evidence = cov == "assessed" or (cov == "unverified_only" and _area_has_eligible(area, flags, run))
            subs = [_score_sub(run, c, area, has_evidence, cov == "unverified_only", flags,
                               context_area=st.status == "context")
                    for c in cfg.areas[area].sub_scores]
        score, frac, formula = _area_formula(subs)
        if cov == "not_assessed":
            score = None  # guard: never score an area without evidence
        score, area_ov = _area_floor(area, score, flags, run, ov)
        if area_ov:
            formula += f"; override: {area_ov[0].label}"
        area_details.append(AreaDetail(area=area, label=label_of.get(area, area), score=score,
                                       level=level_for(score, levels), weight=cfg.areas[area].weight,
                                       coverage_fraction=_r(frac, 4), formula=formula, sub_scores=subs,
                                       contributions=area_ov))
        a_s = AreaScore(area=area, score=score, level=level_for(score, levels), coverage=cov,
                        sub_scores={s.name: s.score for s in subs},
                        method=(NOT_ASSESSED if score is None else f"{formula}; coverage {round_half_even(frac * 100)} %"))
        a_s.trusted_pages = st.trusted_pages_used if st else 0
        a_s.unverified_pages = st.unverified_pages_used if st else 0
        card_areas.append(a_s)

    all_subs = [s for a in area_details for s in a.sub_scores]
    got = [s for s in all_subs if s.score is not None]
    c = sum(s.weight for s in got)
    c_unv = sum(s.weight for s in got if s.unverified_only)
    weighted = sum(s.weight * (s.score or 0) for s in got)
    knockout = any(x.kind == "override" for s in got for x in s.contributions)
    total: int | None = None
    total_ov: list[Contribution] = []
    lo: int | None = None
    hi: int | None = None
    shown = False
    if got:
        lo, hi = round_half_even(weighted), round_half_even(weighted + 100.0 * (1.0 - c))
        if c + 1e-9 >= d.min_coverage:
            total, shown = round_half_even(weighted / c), True
            tformula = (f"weighted average of {len(got)} of {len(all_subs)} sub-scores = {_r(weighted)} / {_r(c)}; "
                        f"coverage {round_half_even(c * 100)} %"
                        + (f" ({round_half_even(c_unv * 100)} % unverified-only)" if c_unv else "")
                        + f"; if unassessed scores were 0 or 100: {lo}-{hi}")
        else:
            tformula = (f"total not shown: coverage {round_half_even(c * 100)} % is below the "
                        f"{round_half_even(d.min_coverage * 100)} % minimum (appendix §A5); possible range {lo}-{hi}")
        if knockout:
            tformula += "; knock-out found: see the verdict"
            floor = round_half_even(ov.knockout_total_floor)
            if total is not None and total < floor:
                ko_ids = ", ".join(x.ref for s in got for x in s.contributions if x.kind == "override")
                total_ov.append(Contribution(
                    kind="override", ref=ko_ids, label=f"knock-out: total {total} raised to {floor}",
                    points=float(floor),
                    rule=(f"a trusted knock-out makes the total at least {floor} (Critical): max(weighted average, "
                          f"{floor}); unverified-only facts never cause a knock-out (scoring.yaml "
                          f"method.overrides; appendix §A5); {OVERRIDE_PRECEDENT}")))
                tformula += f"; override: max({total}, {floor}) = {floor}"
                total = floor
    else:
        tformula = "Not assessed: no sub-score has evidence (never 0)"
    conf_w: dict[str, float] = {"high": 0.0, "medium": 0.0, "low": 0.0}
    for s in got:
        conf_w[s.confidence or "low"] += s.weight
    shares = {k: _r(v / c, 4) if c else 0.0 for k, v in conf_w.items()}
    weights = {a: mp.weight for a, mp in cfg.areas.items()}
    card = ScoreCard(areas=card_areas, total=total, total_level=level_for(total, levels), weights=weights,
                     total_method=tformula)
    return ScoringReport(
        as_of=run.as_of.isoformat(), total=total, total_level=level_for(total, levels), total_shown=shown,
        total_formula=tformula, coverage=_r(c, 4), coverage_unverified_only=_r(c_unv, 4), range_low=lo, range_high=hi,
        knockout=knockout, total_contributions=total_ov, confidence_shares=shares, areas=area_details, constants=d.as_dict(),
        decisions={"anchors (Decision 1)": f"nothing adverse {m.anchors.nothing_adverse:g}, fresh red "
                                           f"{m.anchors.fresh_red_event:g}, fresh amber {m.anchors.fresh_amber_event:g}",
                   "licensed data (Decision 2)": ", ".join(f"{k}={'on' if v else 'off'}"
                                                           for k, v in m.licensed.model_dump().items()),
                   "country basis (Decision 3)": m.country_basis},
        card=card)


# ---------------------------------------------------------------------------
# Public API kept from the seam
# ---------------------------------------------------------------------------


def score_area(area: UmbrellaId, facts: list[Flag], coverage: Coverage, sub_score_names: list[str], *,
               inputs: ScoringInputs | None = None, rules: Rules | None = None, as_of: date | None = None,
               method: MethodConfig | None = None) -> AreaScore:
    """Score one risk area from its verified facts. ``coverage`` 'not_assessed' -> ``score=None``."""
    m = method or load_method()
    names = [n for n in sub_score_names if n in m.sub_scores]
    if not names:
        method_text = NOT_ASSESSED if coverage == "not_assessed" else NOT_SCORED
        return AreaScore(area=area, score=None, level=None, coverage=coverage,
                         sub_scores={n: None for n in sub_score_names}, method=method_text)
    levels = DEFAULT_LEVELS
    run = _Run(m=m, d=derive(m, levels), rules=rules or load_rules(), as_of=as_of or date.today(),
               default_years=_default_years(), inputs=inputs, sources={}, levels=levels)
    if coverage == "not_assessed":
        subs = [_pipeline_not_assessed(run, n, area) for n in names]
    else:
        subs = [_score_sub(run, n, area, True, coverage == "unverified_only", facts) for n in names]
    score, frac, formula = _area_formula(subs)
    score, area_ov = _area_floor(area, score, facts, run, m.overrides)
    if area_ov:
        formula += f"; override: {area_ov[0].label}"
    return AreaScore(area=area, score=score, level=level_for(score), coverage=coverage,
                     sub_scores={s.name: s.score for s in subs},
                     method=NOT_ASSESSED if score is None else f"{formula}; coverage {round_half_even(frac * 100)} %")


def score_total(areas: list[AreaScore], weights: Mapping[str, float], *,
                method: MethodConfig | None = None) -> tuple[int | None, str]:
    """Renormalised weighted total over assessed sub-scores (dataset weights), with the coverage
    minimum. Falls back to area weights for areas without sub-scores."""
    if not weights:
        return None, NOT_SCORED
    m = method or load_method()
    d = derive(m, DEFAULT_LEVELS)
    num = cov = 0.0
    for a in areas:
        if a.sub_scores and all(n in m.sub_scores for n in a.sub_scores):
            for n, s in a.sub_scores.items():
                if s is not None:
                    num += m.sub_scores[n].weight * s
                    cov += m.sub_scores[n].weight
        elif a.score is not None:
            num += weights.get(a.area, 0.0) * a.score
            cov += weights.get(a.area, 0.0)
    if cov == 0:
        return None, "Not assessed: no sub-score has evidence (never 0)"
    if cov + 1e-9 < d.min_coverage:
        return None, (f"total not shown: coverage {round_half_even(cov * 100)} % is below the "
                      f"{round_half_even(d.min_coverage * 100)} % minimum")
    return round_half_even(num / cov), f"weighted average, coverage {round_half_even(cov * 100)} %"


def score_result(flags: list[Flag], areas: list[AreaStatus], cfg: ScoringConfig | None = None, *,
                 inputs: ScoringInputs | None = None, rules: Rules | None = None, as_of: date | None = None,
                 sources: Sequence[Source] | None = None) -> ScoreCard:
    """Score card for result.json. Without ``cfg`` there are no weights, so nothing is scored
    (kept from the seam: callers that pass no config get placeholders)."""
    if cfg is None:
        by_area: dict[UmbrellaId, list[Flag]] = {a: [] for a in UMBRELLAS}
        for f in flags:
            by_area[f.area].append(f)
        status_by_area = {a.area: a for a in areas}
        out: list[AreaScore] = []
        for a in UMBRELLAS:
            st_a = status_by_area.get(a)
            cov = coverage_for(st_a)
            out.append(AreaScore(area=a, score=None, level=None, coverage=cov, sub_scores={},
                                 method=NOT_ASSESSED if cov == "not_assessed" else NOT_SCORED,
                                 trusted_pages=st_a.trusted_pages_used if st_a else 0,
                                 unverified_pages=st_a.unverified_pages_used if st_a else 0))
        return ScoreCard(areas=out, total=None, total_level=None, weights={}, total_method=NOT_SCORED)
    return score_detailed(flags, areas, cfg, inputs=inputs, rules=rules, as_of=as_of, sources=sources).card


# ---------------------------------------------------------------------------
# "How was this scored?" text
# ---------------------------------------------------------------------------


def explain_text(rep: ScoringReport) -> str:
    """Plain-text breakdown for the chatbot's "How was this scored?" button. Deterministic."""
    L: list[str] = [f"How was this scored? (as of {rep.as_of})", ""]
    tot = f"{rep.total} ({rep.total_level})" if rep.total is not None else "not shown"
    L.append(f"Total: {tot}. {rep.total_formula}.")
    for c in rep.total_contributions:
        L.append(f"    · {c.kind} {c.ref}: {c.label} [{c.points:g}] — {c.rule}")
    L.append("Formula in words: each of Siemens's 18 sub-scores is weighted by its dataset weight; sub-scores "
             "with no evidence are left out and the weights of the rest are scaled up to 100 %.")
    L.append("Confidence (share of assessed weight): " + ", ".join(f"{k} {round_half_even(v * 100)} %"
                                                                  for k, v in rep.confidence_shares.items()))
    L.append("Settings: " + "; ".join(f"{k}: {v}" for k, v in rep.decisions.items()))
    L.append("")
    for a in rep.areas:
        head = f"{a.score} ({a.level})" if a.score is not None else "Not assessed"
        L.append(f"## {a.label}: {head}, coverage {round_half_even(a.coverage_fraction * 100)} % of weight {a.weight:g}")
        L.append(f"   {a.formula}")
        for c in a.contributions:
            L.append(f"    · {c.kind} {c.ref}: {c.label} [{c.points:g}] — {c.rule} — source: {c.source}")
        for s in a.sub_scores:
            if s.score is None:
                L.append(f"- {s.name} (weight {s.weight:g}): Not assessed: {s.not_assessed_reason}")
            else:
                tag = " · includes unverified sources" if s.includes_unverified else ""
                L.append(f"- {s.name} (weight {s.weight:g}): {s.score} ({s.level}), confidence {s.confidence}{tag}")
                L.append(f"    {s.formula}")
            for c in s.contributions:
                pts = f" [{c.points:g}]" if c.points is not None else ""
                src = f" — source: {c.source}" if c.source else ""
                L.append(f"    · {c.kind} {c.ref}: {c.label}{pts} — {c.rule}{src}")
        L.append("")
    L.append("Rule constants (derived from the anchors): " + ", ".join(f"{k} {v:g}" for k, v in rep.constants.items()))
    return "\n".join(L).rstrip() + "\n"
