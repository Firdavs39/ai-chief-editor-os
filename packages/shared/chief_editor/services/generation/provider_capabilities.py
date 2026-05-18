"""Per-provider capability metadata + LLMCallOptions.

Phase 2 design (per QUALITY_EDITORIAL_WORKFLOW_PLAN.md §10b):

- `LLMCallOptions` is a backward-compatible dataclass created by the
  workflow engine for each step. Provider capabilities decide which fields
  are used per step (temperature for creative steps vs the judge).
- The actual `LLMProvider.complete_json(system, user, schema, *, temperature)`
  signature is NOT extended in Phase 2 — only `temperature` is forwarded.
  Other LLMCallOptions fields (timeout_seconds, max_tokens, response_mode,
  provider_mode) are captured for future phases when AnthropicProvider /
  OpenAIProvider / OllamaProvider gain per-call timeout / max_tokens
  support without breaking existing call sites.
- Anthropic and OpenAI native Structured Outputs remain an implementation
  spike. Phase 2 treats every real provider as prompt-only JSON with
  `_safe_parse` repair-retry (existing in `OllamaProvider`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ResponseMode = Literal["json", "json_strict"]
ProviderMode = Literal["auto", "force_real", "force_mock"]


@dataclass(frozen=True)
class LLMCallOptions:
    """Per-step call options. Built by the workflow; consumed selectively.

    Phase 2: only `temperature` is forwarded to `provider.complete_json`.
    Other fields are captured for logging/metrics and Phase 3+ wiring.
    """

    step_name: str = ""
    temperature: float | None = None
    timeout_seconds: int | None = None
    max_tokens: int | None = None
    response_mode: ResponseMode = "json"
    provider_mode: ProviderMode = "auto"


@dataclass(frozen=True)
class ProviderCapability:
    """Static per-provider tuning the workflow uses to build LLMCallOptions."""

    name: str
    supports_native_structured_output: bool
    default_temperature: float = 0.7
    judge_temperature: float = 0.2
    default_max_tokens: int = 600
    default_timeout_seconds: int = 180
    step_retry_budget: int = 1


# Phase 2 capability table. `supports_native_structured_output` is False for
# every provider because we have NOT validated the wiring yet (the Anthropic
# `output_config.format` API and OpenAI `response_format` are spikes; Ollama
# Cloud's OpenAI-compat passthrough is unverified). Phase 3+ flips these
# once the corresponding provider class actually emits constrained JSON.
PROVIDER_CAPABILITIES: dict[str, ProviderCapability] = {
    "mock": ProviderCapability(
        name="mock",
        supports_native_structured_output=False,
        default_temperature=0.0,   # deterministic for tests
        judge_temperature=0.0,
        default_max_tokens=2000,
        default_timeout_seconds=30,
        step_retry_budget=0,
    ),
    "ollama": ProviderCapability(
        name="ollama",
        supports_native_structured_output=False,
        default_temperature=0.7,
        judge_temperature=0.2,
        default_max_tokens=600,
        default_timeout_seconds=300,
        step_retry_budget=1,
    ),
    "anthropic": ProviderCapability(
        name="anthropic",
        supports_native_structured_output=False,  # spike — see plan §10
        default_temperature=0.7,
        judge_temperature=0.2,
        default_max_tokens=1000,
        default_timeout_seconds=180,
        step_retry_budget=1,
    ),
    "openai": ProviderCapability(
        name="openai",
        supports_native_structured_output=False,  # capability metadata only
        default_temperature=0.7,
        judge_temperature=0.2,
        default_max_tokens=1000,
        default_timeout_seconds=180,
        step_retry_budget=1,
    ),
}


def get_capability(provider_name: str) -> ProviderCapability:
    return PROVIDER_CAPABILITIES.get(provider_name, PROVIDER_CAPABILITIES["mock"])


def options_for_step(
    provider_name: str,
    step_name: str,
    *,
    is_judge: bool = False,
) -> LLMCallOptions:
    cap = get_capability(provider_name)
    temp = cap.judge_temperature if is_judge else cap.default_temperature
    return LLMCallOptions(
        step_name=step_name,
        temperature=temp,
        timeout_seconds=cap.default_timeout_seconds,
        max_tokens=cap.default_max_tokens,
        response_mode="json",
        provider_mode="auto",
    )


__all__ = [
    "LLMCallOptions",
    "PROVIDER_CAPABILITIES",
    "ProviderCapability",
    "get_capability",
    "options_for_step",
]
