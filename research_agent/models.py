"""Typed data for the research agent (pydantic v2).

Two families live here:

* LLM I/O schemas (``*Output`` classes): what the gatherer and verifier models must
  return. They contain no fields that could change budget, tools or sources.
* Result models: what ``run_research`` returns and what ``result.json`` contains.
"""

from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Fixed vocabularies
# ---------------------------------------------------------------------------

UmbrellaId = Literal["financial", "legal", "country", "people", "operations", "reputation"]
UMBRELLAS: tuple[UmbrellaId, ...] = get_args(UmbrellaId)

EventType = Literal[
    "sanctions_listing",
    "insolvency_filing",
    "fraud_or_corruption_case",
    "regulatory_fine",
    "major_lawsuit",
    "antitrust_settlement",
    "forced_labour_or_human_rights_case",
    "safety_accident",
    "safety_fatality",
    "environmental_violation",
    "data_breach",
    "contract_penalty_or_cancellation",
    "audit_or_accounting_issue",
    "supply_chain_forced_labour_listing",
    "strike_or_labour_dispute",
    "product_recall",
    "cyber_incident",
    "plant_disruption",
    "delivery_failure",
    "credit_downgrade",
    "profit_warning",
    "leadership_scandal",
    "country_risk_elevated",
    "country_risk_low",
    "iris_certified",
    "iso_certified",
    "credit_upgrade_or_strong_results",
    "award_or_major_contract",
    "company_disclosed_risk",
    "other_neutral",
]
EVENT_TYPES: tuple[str, ...] = get_args(EventType)

Severity = Literal["high", "medium", "low"]
Colour = Literal["red", "amber", "green", "neutral"]
EntityMatch = Literal["exact", "group", "namesake", "unclear"]
ClaimStatus = Literal["confirmed", "alleged", "unclear"]
Attribution = Literal["firsthand_official", "named_source", "anonymous_or_rumour", "unclear"]
TierId = Literal["official", "company_own", "major_news", "rail_trade", "country_data"]
# "open_web" is not a tier in sources.yaml: it marks a page found by the open-web pass on a site
# that is not on the allowlist. Such pages always have trust "unverified".
SourceTier = Literal["official", "company_own", "major_news", "rail_trade", "country_data", "open_web"]
Trust = Literal["trusted", "unverified"]
RunStatus = Literal["ok", "needs_clarification", "partial", "error"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# LLM output schemas
# ---------------------------------------------------------------------------


class IdentityCandidate(_Strict):
    legal_name: str = Field(description="Full legal name, e.g. 'Knorr-Bremse AG'.")
    country_code: str = Field(description="ISO 3166-1 alpha-2 code of the registered seat, e.g. 'DE'. Empty if unknown.")
    country_name: str = Field(description="English country name. Empty if unknown.")
    website: str = Field(description="Official website domain, e.g. 'knorr-bremse.com'. Empty if unknown.")
    description: str = Field(description="One short line: what the company does.")
    evidence_source_ids: list[str] = Field(description="IDs of the source blocks that mention this entity.")


class IdentityOutput(_Strict):
    candidates: list[IdentityCandidate]


class PlannedQuery(_Strict):
    slot_id: str = Field(description="The slot_id given in the request. Do not invent new slots.")
    query: str = Field(description="Search query text, max 200 characters, must name the company.")


class PlanOutput(_Strict):
    queries: list[PlannedQuery]


class CandidateFactOut(_Strict):
    claim: str = Field(description="One plain sentence: what happened, to whom, when.")
    quote: str = Field(description="Exact words copied from the source text that support the claim, max 25 words.")
    entity_named: str = Field(description="The company name exactly as the source writes it.")
    event_date: str = Field(description="Date of the event as YYYY-MM-DD, YYYY-MM or YYYY. Empty if not stated.")


NumberKind = Literal["credit_rating", "revenue", "current_assets", "current_liabilities", "retained_earnings", "ebit",
                     "total_equity", "total_liabilities", "total_assets", "fine_amount", "injury_rate", "ecovadis_score"]


class NumberOut(_Strict):
    kind: NumberKind
    value: str = Field(description="The value exactly as written in the quote, e.g. '9,523.4', '4,2', 'A-', 'Baa3', '68'.")
    unit: str = Field(description="Currency and scale as written, e.g. 'EUR million', '€ bn', 'Mio. EUR'; "
                      "for rates the metric unit; empty if none.")
    period: str = Field(description="Fiscal year end or as-of date: YYYY-MM-DD, YYYY-MM or YYYY. Empty if not stated.")
    detail: str = Field(description="credit_rating: the agency (S&P, Moody's or Fitch); injury_rate: the metric "
                        "(TRIR, DART or LTIFR); otherwise empty.")
    outlook: str = Field(description="credit_rating: the outlook if stated (stable, positive, negative); else empty.")
    quote: str = Field(description="Exact words copied from the page that state the value, max 25 words.")


class ExtractOutput(_Strict):
    facts: list[CandidateFactOut]
    numbers: list[NumberOut] = Field(default_factory=list, description="Numbers for scoring found on the page.")


class FactVerdict(_Strict):
    fact_id: str
    supported: bool = Field(description="True only if the quote really states the claim.")
    entity_match: EntityMatch
    relevant: bool = Field(description="True if the fact matters for supplier risk or supplier strength.")
    event_type: EventType
    severity: Severity
    claim_status: ClaimStatus
    event_date: str = Field(description="YYYY-MM-DD, YYYY-MM or YYYY; empty if unknown.")
    summary: str = Field(description="One plain line for a procurement buyer, max 25 words, no speculation.")
    reject_reason: str = Field(description="Short reason if rejected, else empty.")
    # Grading signals, recorded for the later scoring step. They never change the colour.
    publisher_named: bool = Field(description="True if the page names an accountable publisher or author.")
    dated: bool = Field(description="True if the page states when it was published or when the event happened.")
    claim_specific_checkable: bool = Field(description="True if the claim names specifics (who, what, when, amount, "
                                           "case or product) that someone could check.")
    cites_primary_document: bool = Field(description="True if the page cites or links a primary document (court "
                                         "ruling, regulator notice, filing, company report).")
    attribution: Attribution = Field(description="Who the claim comes from: firsthand_official (the authority or the "
                                     "company itself), named_source (a named person or outlet), anonymous_or_rumour "
                                     "(unnamed sources, hearsay, rumour), unclear.")


class VerifyOutput(_Strict):
    verdicts: list[FactVerdict]
    contradicts_claim_under_check: bool = Field(
        default=False, description="Only when a 'Claim under check' is given: true if this page explicitly states the "
        "opposite of that claim (e.g. the listing was never made, the case was dismissed).")


class FollowupPick(_Strict):
    flag_id: str
    question: str = Field(description="What we want to find out, one sentence.")
    query: str = Field(description="Short English search query: the company name plus 2-4 words about the event.")
    query_local: str = Field(description="The same short query in the main language of the company's country; "
                             "repeat the English query if that language is English.")


class FollowupOutput(_Strict):
    picks: list[FollowupPick]


class SummaryOutput(_Strict):
    summary: str = Field(description="2-3 sentences, only from the verified findings provided.")


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class ConfirmedEntity(BaseModel):
    legal_name: str
    country_code: str = ""
    country_name: str = ""
    website: str = ""
    description: str = ""
    evidence_urls: list[str] = Field(default_factory=list)
    confirmed_by: Literal["sources", "user_input"] = "sources"


class ClarificationRequest(BaseModel):
    question: str
    candidates: list[ConfirmedEntity]


class Source(BaseModel):
    id: str
    url: str
    title: str
    publisher: str
    tier: SourceTier
    trust: Trust = Field(default="trusted", description="'trusted' = on the allowlist (incl. company_own); "
                         "'unverified' = not in our trusted source list.")
    published_date: str | None = None
    retrieved_at: str
    found_by: str = Field(description="Plan step id that found this page, e.g. 'legal-1' or 'followup-1'.")
    umbrella: UmbrellaId | None = None
    reliability: Literal["B", "C", "D"] | None = Field(
        default=None, description="Unverified sources only, set by code: C if the page shows a corrections policy "
        "or editorial accountability, else D (appendix §A4 step 2). B (official domain) is decided by scoring.")
    text_origin: Literal["extract", "search_snippet", "data"] = Field(
        default="extract", description="'data' = structured figures read by code (country indices), no model.")


class GradingSignals(BaseModel):
    """Evidence-quality signals for the later scoring step. Not used for colours.

    The first five come from the verifier for the fact's primary source (the first source
    cited). The last two are computed by code across all of the fact's sources."""

    publisher_named: bool = False
    dated: bool = False
    claim_specific_checkable: bool = False
    cites_primary_document: bool = False
    attribution: Attribution = "unclear"
    corroborated_by_trusted: bool = Field(default=False, description="Code: at least 2 independent sources support "
                                          "the fact and at least one of them is trusted.")
    independent_domains: int = Field(default=1, description="Code: distinct domains supporting the fact; same-domain "
                                     "pages, near-identical text and pages sharing a passage of 25 or more consecutive "
                                     "words count once (appendix §A4 guard 4).")
    contradicted_by_trusted: bool = Field(default=False, description="Code: a trusted page explicitly states the "
                                          "opposite (gate E7). Found by trusted follow-ups.")
    excluded_site_type: str | None = Field(default=None, description="Gate E6: denylist category of the site. Always "
                                           "None in practice, because denylisted sites are dropped before reading.")


class Flag(BaseModel):
    id: str
    colour: Colour
    area: UmbrellaId
    event_type: EventType
    severity: Severity
    claim_status: ClaimStatus
    summary: str
    quote: str
    event_date: str | None = None
    source_ids: list[str]
    company_stated: bool = False
    trust: Trust = Field(default="trusted", description="'unverified' when every source for this fact is unverified.")
    capped_unverified: bool = Field(default=False, description="Colour was lowered because only unverified sources support it.")
    knockout: bool = False
    stale: bool = False
    rule_note: str = ""
    quote_context: str | None = Field(default=None, description="The quote with about 200 characters of page text "
                                      "on each side, cut when the fact was verified (for citation popovers).")
    found_in_followup: bool = False
    signals: GradingSignals = Field(default_factory=GradingSignals)
    data: dict[str, Any] | None = Field(default=None, description="Structured value for data facts, e.g. "
                                        "{'indicator': 'GOV_WGI_PV.SC', 'value': 69.3, 'year': 2025, 'scale': '0-100'}.")


class RejectedFact(BaseModel):
    source_id: str
    claim: str
    reason: str


DropReason = Literal["denylisted", "not_allowlisted", "off_topic", "trusted_site_in_open_web", "duplicate",
                     "area_cap", "page_budget", "extract_failed"]


class DroppedResult(BaseModel):
    url: str
    title: str = ""
    reason: DropReason


class PlannedSearch(BaseModel):
    id: str
    umbrella: UmbrellaId | None
    purpose: str
    query: str
    tiers: list[TierId]
    topic: Literal["general", "news"]
    start_date: str | None
    lang: Literal["en", "local"] = "en"
    status: Literal["planned", "done", "skipped", "failed"] = "planned"
    open_web: bool = Field(default=False, description="True for an open-web gap-fill search (no domain restriction).")
    results_kept: int = 0
    results_dropped_not_allowlisted: int = 0
    results_dropped_denylisted: int = 0
    results_dropped_off_topic: int = 0
    dropped: list[DroppedResult] = Field(default_factory=list, description="Every result not read, with the reason.")


class Followup(BaseModel):
    id: str
    flag_id: str
    flag_summary: str
    question: str
    query: str
    query_local: str = ""
    pages_checked: int = 0
    new_flag_ids: list[str] = Field(default_factory=list)
    corroborating_source_ids: list[str] = Field(default_factory=list)
    outcome: str = ""


class AreaStatus(BaseModel):
    area: UmbrellaId
    label: str
    status: Literal["red", "amber", "green", "context", "not_assessed"] = Field(
        description="'context' = only neutral or older (stale) facts: recorded, neither an issue nor a strength.")
    finding: str
    flag_ids: list[str] = Field(default_factory=list)
    pages_checked: int = Field(default=0, description="Trusted pages read for this area's searches.")
    unverified_pages_checked: int = 0
    trusted_pages_used: int = Field(default=0, description="Trusted pages that gave at least one verified fact "
                                    "for this area. 0 means the area is not assessed.")
    unverified_pages_used: int = 0


ScoreLevel = Literal["Low", "Medium", "High", "Critical"]
Coverage = Literal["assessed", "unverified_only", "not_assessed"]


class AreaScore(BaseModel):
    """Placeholder for the 0-100 risk score of one area (0 = no risk, 100 = maximum risk).

    ``score`` stays None until the facts-to-scores method is agreed. An area with coverage
    "not_assessed" is never scored, and in particular never 0."""

    area: UmbrellaId
    score: int | None = None
    level: ScoreLevel | None = Field(default=None, description="Low 0-24, Medium 25-49, High 50-74, Critical 75-100.")
    coverage: Coverage = Field(default="not_assessed", description="'assessed' = at least one trusted page gave a "
                               "verified fact for the area; 'unverified_only' = only unverified pages did; "
                               "'not_assessed' = no page did.")
    trusted_pages: int = 0
    unverified_pages: int = 0
    sub_scores: dict[str, int | None] = Field(default_factory=dict, description="Dataset score columns mapped to "
                                              "this area (config/scoring.yaml), e.g. 'Financial_Health_Score'.")
    method: str = "not scored yet"


class ScoreCard(BaseModel):
    """Per-area scores and the weighted total. Filled by ``scoring.score_result``."""

    areas: list[AreaScore] = Field(default_factory=list)
    total: int | None = None
    total_level: ScoreLevel | None = None
    weights: dict[str, float] = Field(default_factory=dict, description="Area weights used for the total.")
    coverage: float | None = Field(default=None, description="Share of sub-score weight assessed, 0-1.")
    range_low: int | None = Field(default=None, description="Total if every unassessed sub-score were 0.")
    range_high: int | None = Field(default=None, description="Total if every unassessed sub-score were 100.")
    total_method: str = "not scored yet"


class NumericFact(BaseModel):
    """One number read from a page for the scoring step, with its checks."""

    kind: NumberKind
    value: str
    amount: float | None = Field(default=None, description="Parsed value in base units (e.g. EUR, not EUR million); "
                                 "None for a rating.")
    currency: str = ""
    unit: str = ""
    period: str | None = None
    detail: str = ""
    outlook: str = ""
    quote: str
    source_id: str
    trust: Trust = "trusted"
    company_stated: bool = False
    accepted: bool = True
    reject_reason: str = ""


class ProgressEvent(BaseModel):
    kind: Literal["identity", "plan", "search", "extract", "verify", "followup", "report", "warning", "done"]
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    elapsed_s: float = 0.0


class RunStats(BaseModel):
    searches_used: int = 0
    extracts_used: int = 0
    followups_used: int = 0
    pages_read: int = 0
    trusted_pages_read: int = 0
    unverified_pages_read: int = 0
    results_dropped_not_allowlisted: int = 0
    results_dropped_denylisted: int = 0
    results_dropped_off_topic: int = 0
    drop_reasons: dict[str, int] = Field(default_factory=dict, description="Results not read, counted by reason.")
    cache_hits: int = 0
    candidate_facts: int = 0
    rejected_quote_not_found: int = 0
    rejected_by_verifier: int = 0
    rejected_namesake_or_unclear_entity: int = 0
    rejected_irrelevant: int = 0
    verified_facts: int = 0
    llm_errors: int = 0
    elapsed_s: float = 0.0


class ResearchResult(BaseModel):
    status: RunStatus
    company_input: str
    country_input: str | None = None
    website_input: str | None = None
    researched_at: str
    entity: ConfirmedEntity | None = None
    clarification: ClarificationRequest | None = None
    verdict: str = ""
    summary: str = ""
    flags: list[Flag] = Field(default_factory=list)
    areas: list[AreaStatus] = Field(default_factory=list)
    scores: ScoreCard = Field(default_factory=ScoreCard)
    followups: list[Followup] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    plan: list[PlannedSearch] = Field(default_factory=list)
    trail: list[ProgressEvent] = Field(default_factory=list)
    rejected: list[RejectedFact] = Field(default_factory=list)
    stats: RunStats = Field(default_factory=RunStats)
    warnings: list[str] = Field(default_factory=list)
    models: dict[str, str] = Field(default_factory=dict)
    notice: str | None = Field(default=None, description="Banner shown at the top of the report, e.g. fixture data.")
    numeric_facts: list[NumericFact] = Field(default_factory=list, description="Numbers read for scoring, "
                                             "accepted and rejected, with quotes.")
    scoring_inputs: dict[str, Any] | None = Field(default=None, description="scoring_inputs.ScoringInputs as JSON.")
    scoring_detail: dict[str, Any] | None = Field(default=None, description="scoring.ScoringReport as JSON, for "
                                                  "'How was this scored?' (ScoringReport.model_validate + explain_text).")
    fingerprint: dict[str, Any] = Field(default_factory=dict, description="Config hash, models, cache day and query "
                                        "list, so two runs can be compared (python -m research_agent.diff_runs).")
