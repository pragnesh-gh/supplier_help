"""Tiny LLM adapter.

The pipeline only needs one operation: "given a system prompt and a user message,
return an instance of this pydantic schema". Any provider that can do structured
output can implement :class:`LLM` (e.g. Nemotron via OpenRouter later).
"""

from __future__ import annotations

import os
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

Role = Literal["gatherer", "verifier"]
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model call failed or returned nothing usable."""


class LLM(Protocol):
    def structured(self, *, role: Role, system: str, user: str, schema: type[T]) -> T: ...

    def model_name(self, role: Role) -> str: ...


class AnthropicLLM:
    """Claude via the official ``anthropic`` SDK, using structured outputs.

    ``client.messages.parse(output_format=<pydantic class>)`` sends the schema as
    ``output_config.format`` and returns the validated object in ``parsed_output``
    (verified against platform.claude.com docs and SDK 1.15.0 source, 2026-10-18).

    Effort is sent as ``output_config={"effort": ...}``. ``messages.parse`` merges that dict
    with the schema it builds from ``output_format`` into one ``output_config`` (checked in the
    SDK 1.15.0 source). ``thinking`` is not sent: on Sonnet 5.5 and Opus 5.5 omitting it means
    adaptive thinking, and disabling it is rejected; effort is the control.
    """

    def __init__(
        self,
        gatherer_model: str,
        verifier_model: str,
        max_tokens: int = 16000,
        timeout_s: float = 60.0,
        api_key: str | None = None,
        gatherer_effort: str | None = None,
        verifier_effort: str | None = None,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise LLMError("The 'anthropic' package is not installed; pip install -r research_agent/requirements.txt") from exc
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=key, timeout=timeout_s, max_retries=2)
        self._models: dict[Role, str] = {"gatherer": gatherer_model, "verifier": verifier_model}
        self._effort: dict[Role, str | None] = {"gatherer": gatherer_effort, "verifier": verifier_effort}
        self._max_tokens = max_tokens

    def model_name(self, role: Role) -> str:
        return self._models[role]

    def structured(self, *, role: Role, system: str, user: str, schema: type[T]) -> T:
        extra: dict[str, Any] = {}
        effort = self._effort[role]
        if effort:
            extra["output_config"] = {"effort": effort}
        try:
            response = self._client.messages.parse(
                model=self._models[role],
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                **extra,
            )
        except self._anthropic.APIError as exc:
            # Never include request headers (API key) in the message.
            raise LLMError(f"{role} model call failed: {type(exc).__name__}: {getattr(exc, 'message', '')}") from None
        except Exception as exc:  # pydantic validation of model output, etc.
            raise LLMError(f"{role} model returned unusable output: {type(exc).__name__}") from None
        if response.stop_reason in ("refusal", "max_tokens"):
            raise LLMError(f"{role} model stopped early: {response.stop_reason}")
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"{role} model returned no structured output")
        if not isinstance(parsed, schema):
            raise LLMError(f"{role} model returned the wrong type")
        return parsed
