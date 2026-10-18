"""Load and validate the YAML config files (settings, sources, rules)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import EVENT_TYPES, UMBRELLAS, TierId

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


class ModelSettings(_M):
    gatherer: str
    verifier: str
    max_output_tokens: int = 4096


class BudgetSettings(_M):
    wall_clock_seconds: float = 120
    max_searches: int = 12
    max_extracts: int = 12
    extracts_reserved_for_followups: int = 4
    max_followups: int = 2
    pages_per_followup: int = 2
    max_results_per_search: int = 8
    max_pages_per_umbrella: int = 3
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
    query: str


class UmbrellaSettings(_M):
    label: str
    searches: list[SearchTemplate]


class IdentitySettings(_M):
    tiers: list[TierId]
    max_candidates_shown: int = 5


class Settings(_M):
    models: ModelSettings
    budget: BudgetSettings
    recency: RecencySettings
    tavily: TavilySettings
    umbrellas: dict[str, UmbrellaSettings]
    identity: IdentitySettings

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
# sources.yaml -> Allowlist
# ---------------------------------------------------------------------------


def domain_of(url_or_domain: str) -> str:
    """Return the lower-case host without 'www.' for a URL or bare domain."""
    s = url_or_domain.strip().lower()
    if "//" not in s:
        s = "//" + s
    host = urlsplit(s).hostname or ""
    return host.removeprefix("www.").rstrip(".")


@dataclass(frozen=True)
class AllowedSource:
    tier: TierId
    publisher: str
    domain: str


@dataclass
class Allowlist:
    """Domain -> tier/publisher lookup. Subdomains match their parent entry."""

    tiers: dict[TierId, dict[str, str]]
    priority: dict[TierId, int] = field(default_factory=dict)
    labels: dict[TierId, str] = field(default_factory=dict)

    def with_company(self, website: str, publisher: str) -> Allowlist:
        dom = domain_of(website)
        tiers: dict[TierId, dict[str, str]] = {t: dict(d) for t, d in self.tiers.items()}
        if dom:
            tiers["company_own"] = {dom: publisher}
        return Allowlist(tiers=tiers, priority=dict(self.priority), labels=dict(self.labels))

    def match(self, url: str) -> AllowedSource | None:
        host = domain_of(url)
        if not host:
            return None
        if not url.lower().startswith(("https://", "http://")):
            return None
        best: AllowedSource | None = None
        for tier, domains in self.tiers.items():
            for dom, publisher in domains.items():
                if host == dom or host.endswith("." + dom):
                    if best is None or len(dom) > len(best.domain):
                        best = AllowedSource(tier=tier, publisher=publisher, domain=dom)
        return best

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
    return Allowlist(tiers=tiers, priority=priority, labels=labels)


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


def load_all() -> AgentConfig:
    return AgentConfig(settings=load_settings(), rules=load_rules(), allowlist=load_allowlist())
