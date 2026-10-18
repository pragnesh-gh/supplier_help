"""Load and validate the YAML config files (settings, sources, rules)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast, get_args
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import EVENT_TYPES, UMBRELLAS, SourceTier, TierId, Trust, UmbrellaId

CONFIG_DIR = Path(__file__).parent / "config"
PROMPTS_DIR = Path(__file__).parent / "prompts"
TIER_IDS: tuple[TierId, ...] = ("official", "company_own", "major_news", "rail_trade", "country_data")


class ConfigError(ValueError):
    """Raised when a config file is missing or invalid."""


# ---------------------------------------------------------------------------
# settings.yaml
# ---------------------------------------------------------------------------


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


Effort = Literal["low", "medium", "high", "xhigh", "max"]


class ModelSettings(_M):
    gatherer: str
    verifier: str
    # Sent as output_config.effort; None means "do not send it" (the model's own default).
    gatherer_effort: Effort | None = "medium"
    verifier_effort: Effort | None = "medium"
    max_output_tokens: int = 16000


class BudgetSettings(_M):
    wall_clock_seconds: float = 120
    max_searches: int = 12
    max_extracts: int = 12
    extracts_reserved_for_followups: int = 4
    max_followups: int = 2
    pages_per_followup: int = 2
    max_results_per_search: int = 8
    max_trusted_pages: int = 12
    llm_timeout_seconds: float = 60
    search_timeout_seconds: float = 30
    parallel_workers: int = 6


class RecencySettings(_M):
    default_years: int = 3
    legal_years: int = 10


class TavilySettings(_M):
    base_url: str = "https://api.tavily.com"
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "advanced"
    extract_depth: Literal["basic", "advanced"] = "basic"


class SearchTemplate(_M):
    tiers: list[TierId]
    topic: Literal["general", "news"]
    lookback: Literal["default", "legal"]
    lang: Literal["en", "local"] = "en"
    query: str
    local: dict[str, str] = Field(default_factory=dict)  # language code -> fixed translation


class UmbrellaSettings(_M):
    label: str
    searches: list[SearchTemplate]
    prefer_recent: bool = False  # newest pages first within the area


class OpenWebSettings(_M):
    enabled: bool = True
    # Areas that may get an open-web gap-fill search, in priority order (ties go to the earlier one).
    umbrellas: list[UmbrellaId] = Field(default_factory=lambda: list[UmbrellaId](["reputation", "people", "operations", "legal", "financial"]))
    max_searches: int = 2
    max_pages: int = 2
    max_pages_per_umbrella: int = 1


class CountryDataSettings(_M):
    wgi_source: Literal["tavily", "worldbank_api", "off"] = "tavily"
    wgi_indicators: list[str] = Field(default_factory=lambda: ["GOV_WGI_PV.SC", "GOV_WGI_CC.SC", "GOV_WGI_RL.SC"])
    cpi_file: str | None = "data/country/CPI2025_Results.xlsx"
    cpi_year: int = 2025
    cpi_url: str = "https://www.transparency.org/en/cpi/2025"
    cpi_published: str = "2026-02-10"
    elevated_below: float = 33.3
    low_at_or_above: float = 66.7


class CacheSettings(_M):
    enabled: bool = True
    dir: str = "output/.cache"


class IdentitySettings(_M):
    tiers: list[TierId]
    max_candidates_shown: int = 5


class ProfileSettings(_M):
    enabled: bool = True
    # One extra trusted search, only when the pages already read did not state these fields.
    required: list[str] = Field(default_factory=lambda: ["description", "headquarters", "founded"])
    tiers: list[TierId] = Field(default_factory=lambda: list[TierId](["company_own", "official", "rail_trade"]))
    query: str = "{company} company profile headquarters founded products"
    max_searches: int = 1
    max_pages: int = 2
    # Skip the extra search when less time than this is left, so the red-flag follow-ups keep theirs.
    min_seconds_left: float = 45


class Settings(_M):
    models: ModelSettings
    budget: BudgetSettings
    recency: RecencySettings
    tavily: TavilySettings
    umbrellas: dict[str, UmbrellaSettings]
    identity: IdentitySettings
    open_web: OpenWebSettings = Field(default_factory=OpenWebSettings)
    profile: ProfileSettings = Field(default_factory=ProfileSettings)
    max_query_extra_words: int = 5
    country_languages: dict[str, str] = Field(default_factory=dict)
    country_data: CountryDataSettings = Field(default_factory=CountryDataSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    injury_benchmarks: dict[str, dict[str, Any]] = Field(default_factory=dict)
    english_speaking_countries: list[str] = Field(default_factory=lambda: ["GB", "UK", "US", "IE", "AU", "NZ"])

    @field_validator("umbrellas")
    @classmethod
    def _six_umbrellas(cls, v: dict[str, UmbrellaSettings]) -> dict[str, UmbrellaSettings]:
        if set(v) != set(UMBRELLAS):
            raise ValueError(f"umbrellas must be exactly {sorted(UMBRELLAS)}, got {sorted(v)}")
        return v


# ---------------------------------------------------------------------------
# rules.yaml
# ---------------------------------------------------------------------------


class EventRule(_M):
    colour: Literal["red", "amber", "green", "neutral"]
    area: str
    knockout: bool = False
    stale_after_years: int | Literal["never"] | None = None


class VerdictTexts(_M):
    knockout: str
    red: str
    amber: str
    none: str
    no_evidence: str


class Rules(_M):
    event_types: dict[str, EventRule]
    verdict: VerdictTexts
    next_steps: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_types")
    @classmethod
    def _all_event_types(cls, v: dict[str, EventRule]) -> dict[str, EventRule]:
        missing = set(EVENT_TYPES) - set(v)
        extra = set(v) - set(EVENT_TYPES)
        if missing or extra:
            raise ValueError(f"rules.yaml event types mismatch; missing={sorted(missing)} unknown={sorted(extra)}")
        for name, rule in v.items():
            if rule.area not in (*UMBRELLAS, "from_search"):
                raise ValueError(f"event type {name}: unknown area {rule.area!r}")
        return v


# ---------------------------------------------------------------------------
# scoring.yaml (placeholders only; no scoring method)
# ---------------------------------------------------------------------------


class ScoreBand(_M):
    name: Literal["Low", "Medium", "High", "Critical"]
    min: int


class ScoreAreaMap(_M):
    dataset_umbrella: str
    weight: float
    sub_scores: list[str] = Field(default_factory=list)


class ScoringConfig(_M):
    levels: list[ScoreBand]
    areas: dict[UmbrellaId, ScoreAreaMap]
    # Room for scoring_method.yaml to merge into scoring.yaml later; the files stay separate now.
    method: dict[str, Any] | None = None

    @field_validator("areas")
    @classmethod
    def _all_areas_weights(cls, v: dict[UmbrellaId, ScoreAreaMap]) -> dict[UmbrellaId, ScoreAreaMap]:
        if set(v) != set(UMBRELLAS):
            raise ValueError(f"scoring areas must be exactly {sorted(UMBRELLAS)}, got {sorted(v)}")
        total = sum(a.weight for a in v.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"scoring weights must add up to 1.0, got {total:.3f}")
        return v


def load_scoring(path: Path | None = None) -> ScoringConfig:
    data = _read_yaml(path or CONFIG_DIR / "scoring.yaml")
    try:
        return ScoringConfig.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"scoring.yaml invalid: {exc}") from exc


# ---------------------------------------------------------------------------
# sources.yaml -> Allowlist
# ---------------------------------------------------------------------------


def domain_of(url_or_domain: str) -> str:
    """Return the lower-case host without 'www.' for a URL or bare domain."""
    s = url_or_domain.strip().lower()
    if "//" not in s:
        s = "//" + s
    host = urlsplit(s).hostname or ""
    return host.removeprefix("www.").rstrip(".")


OPEN_WEB_PRIORITY = 99  # unverified pages always rank after every trusted tier


@dataclass(frozen=True)
class SourceMatch:
    """How a URL is classified: its tier, publisher and trust label."""

    tier: SourceTier
    publisher: str
    domain: str
    trust: Trust = "trusted"


AllowedSource = SourceMatch  # older name, kept for callers


def _host_matches(host: str, dom: str) -> bool:
    return host == dom or host.endswith("." + dom)


@dataclass
class Allowlist:
    """Domain -> tier/publisher lookup plus the denylist. Subdomains match their parent entry."""

    tiers: dict[TierId, dict[str, str]]
    priority: dict[TierId, int] = field(default_factory=dict)
    labels: dict[TierId, str] = field(default_factory=dict)
    denied: dict[str, str] = field(default_factory=dict)  # domain -> denylist category

    def with_company(self, website: str, publisher: str) -> Allowlist:
        dom = domain_of(website)
        tiers: dict[TierId, dict[str, str]] = {t: dict(d) for t, d in self.tiers.items()}
        if dom and self.denied_category("https://" + dom) is None:
            tiers["company_own"] = {dom: publisher}
        return Allowlist(tiers=tiers, priority=dict(self.priority), labels=dict(self.labels), denied=dict(self.denied))

    def denied_category(self, url: str) -> str | None:
        """Denylist category ('social_media', 'forums', ...) if the URL's site is blocked."""
        host = domain_of(url)
        best = ""
        for dom in self.denied:
            if _host_matches(host, dom) and len(dom) > len(best):
                best = dom
        return self.denied[best] if best else None

    def match(self, url: str) -> SourceMatch | None:
        """Trusted match only: the allowlist entry for this URL, or None."""
        host = domain_of(url)
        if not host:
            return None
        if not url.lower().startswith(("https://", "http://")):
            return None
        best: SourceMatch | None = None
        for tier, domains in self.tiers.items():
            for dom, publisher in domains.items():
                if _host_matches(host, dom):
                    if best is None or len(dom) > len(best.domain):
                        best = SourceMatch(tier=tier, publisher=publisher, domain=dom)
        return best

    def classify(self, url: str) -> SourceMatch | None:
        """Classify any URL. None = never use it (denylisted, or not an http(s) URL).
        Denylist is checked first, so a blocked site can never come back as trusted."""
        host = domain_of(url)
        if not host or not url.lower().startswith(("https://", "http://")):
            return None
        if self.denied_category(url) is not None:
            return None
        trusted = self.match(url)
        if trusted is not None:
            return trusted
        return SourceMatch(tier="open_web", publisher=host, domain=host, trust="unverified")

    def rank(self, m: SourceMatch) -> int:
        """Sort key: lower = read and cited first."""
        if m.tier == "open_web":
            return OPEN_WEB_PRIORITY
        return self.priority.get(m.tier, 9)

    def denied_domains(self) -> list[str]:
        return sorted(self.denied)

    def domains_for(self, tiers: list[TierId]) -> list[str]:
        out: list[str] = []
        for t in tiers:
            out.extend(self.tiers.get(t, {}).keys())
        return out


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"{path.name}: expected a mapping at top level")
    return cast(dict[str, Any], data)


def load_allowlist(path: Path | None = None) -> Allowlist:
    data = _read_yaml(path or CONFIG_DIR / "sources.yaml")
    raw = data.get("tiers")
    if not isinstance(raw, dict):
        raise ConfigError("sources.yaml: 'tiers' mapping missing")
    tiers: dict[TierId, dict[str, str]] = {}
    priority: dict[TierId, int] = {}
    labels: dict[TierId, str] = {}
    for tier_name, body in raw.items():
        if tier_name not in TIER_IDS:
            raise ConfigError(f"sources.yaml: unknown tier {tier_name!r}; allowed: {TIER_IDS}")
        tier = cast(TierId, tier_name)
        body = body or {}
        domains = body.get("domains") or {}
        if not isinstance(domains, dict):
            raise ConfigError(f"sources.yaml: tier {tier}: 'domains' must be a mapping domain -> publisher")
        tiers[tier] = {domain_of(str(d)): str(p) for d, p in domains.items()}
        priority[tier] = int(body.get("priority", 9))
        labels[tier] = str(body.get("label", tier))
    for t in TIER_IDS:
        tiers.setdefault(t, {})
    denied = _load_denylist(data.get("denylist"))
    trusted_domains = {d for doms in tiers.values() for d in doms}
    clash = sorted(trusted_domains & set(denied))
    if clash:
        raise ConfigError(f"sources.yaml: domains are both trusted and denylisted: {clash}")
    return Allowlist(tiers=tiers, priority=priority, labels=labels, denied=denied)


def _load_denylist(raw: Any) -> dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("sources.yaml: 'denylist' must map category -> list of domains")
    denied: dict[str, str] = {}
    for category, domains in raw.items():
        if not isinstance(domains, list):
            raise ConfigError(f"sources.yaml: denylist {category}: expected a list of domains")
        for d in domains:
            dom = domain_of(str(d))
            if dom:
                denied[dom] = str(category)
    return denied


def load_settings(path: Path | None = None) -> Settings:
    data = _read_yaml(path or CONFIG_DIR / "settings.yaml")
    try:
        settings = Settings.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"settings.yaml invalid: {exc}") from exc
    env_g = os.environ.get("RESEARCH_GATHERER_MODEL")
    env_v = os.environ.get("RESEARCH_VERIFIER_MODEL")
    if env_g:
        settings.models.gatherer = env_g
    if env_v:
        settings.models.verifier = env_v
    for role in ("gatherer", "verifier"):
        env_e = os.environ.get(f"RESEARCH_{role.upper()}_EFFORT")
        if env_e:
            if env_e not in get_args(Effort):
                raise ConfigError(f"RESEARCH_{role.upper()}_EFFORT must be one of {get_args(Effort)}")
            setattr(settings.models, f"{role}_effort", env_e)
    return settings


def load_rules(path: Path | None = None) -> Rules:
    data = _read_yaml(path or CONFIG_DIR / "rules.yaml")
    try:
        return Rules.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"rules.yaml invalid: {exc}") from exc


def load_prompt(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise ConfigError(f"missing prompt file: {path}")
    return path.read_text(encoding="utf-8")


@dataclass
class AgentConfig:
    settings: Settings
    rules: Rules
    allowlist: Allowlist
    scoring: ScoringConfig | None = None


def load_all() -> AgentConfig:
    cfg = AgentConfig(settings=load_settings(), rules=load_rules(), allowlist=load_allowlist(), scoring=load_scoring())
    if cfg.scoring is not None:  # one name per area in every output
        for area, m in cfg.scoring.areas.items():
            label = cfg.settings.umbrellas[area].label
            if label != m.dataset_umbrella:
                raise ConfigError(f"settings.yaml label {label!r} for {area} must equal scoring.yaml "
                                  f"dataset_umbrella {m.dataset_umbrella!r}")
    return cfg
