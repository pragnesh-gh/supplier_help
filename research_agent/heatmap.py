"""Likelihood x severity heatmap for red flags and watch items. Deterministic.

Severity comes from the flag colour (and the verifier's severity label), likelihood from how
well the fact is verified. The table lives in ``config/report.yaml`` ("heatmap"), so the
report, the docs and the code all use one rule. No model is involved.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import Flag

CONFIG_PATH = Path(__file__).parent / "config" / "report.yaml"
WHEN_KEYS = ("colour", "verifier_severity", "trust", "claim_status", "corroborated", "firsthand")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Rule(_M):
    when: dict[str, Any] = Field(default_factory=dict)
    then: str

    @model_validator(mode="after")
    def _known_keys(self) -> Rule:
        bad = set(self.when) - set(WHEN_KEYS)
        if bad:
            raise ValueError(f"unknown heatmap condition(s): {sorted(bad)}")
        return self


class HeatmapRule(_M):
    severity_levels: list[str]
    likelihood_levels: list[str]
    labels: dict[str, str]
    severity_rules: list[Rule]
    likelihood_rules: list[Rule]
    priority: dict[str, dict[str, int]]
    priority_labels: dict[int, str]

    @model_validator(mode="after")
    def _complete(self) -> HeatmapRule:
        for r in self.severity_rules:
            if r.then not in self.severity_levels:
                raise ValueError(f"severity rule gives unknown level {r.then!r}")
        for r in self.likelihood_rules:
            if r.then not in self.likelihood_levels:
                raise ValueError(f"likelihood rule gives unknown level {r.then!r}")
        for s in self.severity_levels:
            for li in self.likelihood_levels:
                p = self.priority.get(s, {}).get(li)
                if p is None or p not in self.priority_labels:
                    raise ValueError(f"priority missing for {s} x {li}")
            if s not in self.labels:
                raise ValueError(f"label missing for {s}")
        for li in self.likelihood_levels:
            if li not in self.labels:
                raise ValueError(f"label missing for {li}")
        return self


@lru_cache(maxsize=4)
def _load(path: str) -> HeatmapRule:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return HeatmapRule.model_validate(raw["heatmap"])


def load_rule(path: Path | None = None) -> HeatmapRule:
    return _load(str(path or CONFIG_PATH))


def _facts(f: Flag) -> dict[str, Any]:
    s = f.signals
    trusted = f.trust == "trusted"
    return {
        "colour": f.colour,
        "verifier_severity": f.severity,
        "trust": f.trust,
        "claim_status": f.claim_status,
        "corroborated": trusted and (s.corroborated_by_trusted or s.independent_domains >= 2),
        "firsthand": trusted and s.attribution == "firsthand_official",
    }


def _matches(when: dict[str, Any], facts: dict[str, Any]) -> bool:
    for key, want in when.items():
        have = facts[key]
        if isinstance(want, list):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def _first(rules: list[Rule], facts: dict[str, Any], fallback: str) -> str:
    return next((r.then for r in rules if _matches(r.when, facts)), fallback)


def severity_of(f: Flag, rule: HeatmapRule | None = None) -> str:
    rule = rule or load_rule()
    return _first(rule.severity_rules, _facts(f), rule.severity_levels[-1])


def likelihood_of(f: Flag, rule: HeatmapRule | None = None) -> str:
    rule = rule or load_rule()
    return _first(rule.likelihood_rules, _facts(f), rule.likelihood_levels[0])


def placed(f: Flag) -> bool:
    """Only red flags and watch items go on the heatmap."""
    return f.colour in ("red", "amber")


def priority_of(f: Flag, rule: HeatmapRule | None = None) -> int:
    rule = rule or load_rule()
    return rule.priority[severity_of(f, rule)][likelihood_of(f, rule)]


# ---------------------------------------------------------------------------
# Plain-English description of the table (printed in the report's method section)
# ---------------------------------------------------------------------------

_COND_TEXT = {
    ("colour", "red"): "red flag",
    ("colour", "amber"): "watch item",
    ("trust", "unverified"): "found only on sites not in our trusted source list",
    ("trust", "trusted"): "backed by a trusted source",
    ("corroborated", True): "confirmed by at least two independent sources, one of them trusted",
    ("corroborated", False): "not confirmed by a second source",
    ("firsthand", True): "stated by the authority or the company itself",
    ("firsthand", False): "not stated first-hand",
}


def _cond(key: str, want: Any) -> str:
    if isinstance(want, list):
        return " or ".join(_cond(key, w) for w in want)
    if (key, want) in _COND_TEXT:
        return _COND_TEXT[(key, want)]
    if key == "verifier_severity":
        return f"rated {want} severity"
    if key == "claim_status":
        return f"claim {want}"
    return f"{key} {want}"


def describe(rule: HeatmapRule | None = None) -> dict[str, list[tuple[str, str]]]:
    """Each rule as (condition, result) in reading order, for the report's method section."""
    rule = rule or load_rule()

    def rows(rules: list[Rule], other: str) -> list[tuple[str, str]]:
        out = []
        for r in rules:
            cond = ", ".join(_cond(k, v) for k, v in r.when.items()) if r.when else other
            out.append((cond[:1].upper() + cond[1:], rule.labels[r.then]))
        return out

    return {"severity": rows(rule.severity_rules, "any other case"),
            "likelihood": rows(rule.likelihood_rules, "any other case (one trusted source)")}
