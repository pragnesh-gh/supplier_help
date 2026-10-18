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
    "forced_labour_or_human_rights_case",
    "safety_accident",
    "strike_or_labour_dispute",
    "product_recall",
    "cyber_incident",
    "plant_disruption",
    "delivery_failure",
    "credit_downgrade",
    "profit_warning",
    "leadership_scandal",
    "country_risk_elevated",
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
TierId = Literal["official", "company_own", "major_news", "rail_trade", "country_data"]
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


class ExtractOutput(_Strict):
    facts: list[CandidateFactOut]


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


class VerifyOutput(_Strict):
    verdicts: list[FactVerdict]


class FollowupPick(_Strict):
    flag_id: str
    question: str = Field(description="What we want to find out, one sentence.")
    query: str = Field(description="Narrow search query, max 150 characters, naming the company and the event.")


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
    tier: TierId
    published_date: str | None = None
    retrieved_at: str
    found_by: str = Field(description="Plan step id that found this page, e.g. 'legal-1' or 'followup-1'.")
    umbrella: UmbrellaId | None = None
    text_origin: Literal["extract", "search_snippet"] = "extract"


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
    knockout: bool = False
    stale: bool = False
    rule_note: str = ""
    found_in_followup: bool = False


class RejectedFact(BaseModel):
    source_id: str
    claim: str
    reason: str


class PlannedSearch(BaseModel):
    id: str
    umbrella: UmbrellaId | None
    purpose: str
    query: str
    tiers: list[TierId]
    topic: Literal["general", "news"]
    start_date: str | None
    status: Literal["planned", "done", "skipped", "failed"] = "planned"
    results_kept: int = 0
    results_dropped_not_allowlisted: int = 0


class Followup(BaseModel):
    id: str
    flag_id: str
    flag_summary: str
    question: str
    query: str
    pages_checked: int = 0
    new_flag_ids: list[str] = Field(default_factory=list)
    corroborating_source_ids: list[str] = Field(default_factory=list)
    outcome: str = ""


class AreaStatus(BaseModel):
    area: UmbrellaId
    label: str
    status: Literal["red", "amber", "green", "not_assessed"]
    finding: str
    flag_ids: list[str] = Field(default_factory=list)
    pages_checked: int = 0


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
    results_dropped_not_allowlisted: int = 0
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
