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


# ---------------------------------------------------------------------------
# Per-role temperature (audit refactor, May 2026).
#
# Replaces the single 0.7 default with role-band temperatures derived from
# the role's job, not a global knob:
#   - writer roles: 0.6 — Kimi K2-Instruct doc recommends 0.6 for creative
#     generation (lower than 0.7 reduces slop without flattening voice).
#   - evaluative roles (critic, fact_checker, quality_judge): 0.2 — scoring
#     and grounding must be as deterministic as the provider allows.
#   - analytical roles (research, trend, audience psychology): 0.3 — some
#     spread for ideation, but anchored to the source facts.
#
# A real provider with deterministic-leaning capability (mock) overrides
# these with 0.0 so tests stay reproducible — see `options_for_step`.
# ---------------------------------------------------------------------------

WRITER_TEMPERATURE: float = 0.6
EVALUATOR_TEMPERATURE: float = 0.2
ANALYST_TEMPERATURE: float = 0.3

_WRITER_STEPS = frozenset(
    {
        "platform_writer_telegram",
        "platform_writer_threads",
        "platform_writer_reddit",
        "editor_in_chief_draft",
    }
)
_EVALUATOR_STEPS = frozenset(
    {
        "critic_red_team",
        "fact_checker",
        "quality_judge",
    }
)
_ANALYST_STEPS = frozenset(
    {
        "research_analyst",
        "trend_strategist",
        "audience_psychology_analyst",
    }
)


def temperature_for_role(step_name: str) -> float | None:
    """Per-role temperature band, or None if the step is not role-mapped.

    Returning None lets `options_for_step` fall back to the provider's
    default/judge temperature (preserves behaviour for unknown step names
    and keeps the mock provider's deterministic 0.0 override intact).
    """
    if step_name in _WRITER_STEPS:
        return WRITER_TEMPERATURE
    if step_name in _EVALUATOR_STEPS:
        return EVALUATOR_TEMPERATURE
    if step_name in _ANALYST_STEPS:
        return ANALYST_TEMPERATURE
    return None


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
    """Build per-step call options.

    Temperature resolution order:
      1. Mock provider → always its capability temperatures (0.0) so tests
         stay deterministic regardless of the role band.
      2. Real provider → the per-role band from `temperature_for_role`
         (writer 0.6 / evaluator 0.2 / analyst 0.3).
      3. Unmapped step on a real provider → fall back to the provider's
         judge/default temperature (legacy behaviour).
    """
    cap = get_capability(provider_name)
    fallback_temp = cap.judge_temperature if is_judge else cap.default_temperature

    if provider_name == "mock":
        # Deterministic-by-contract provider: ignore the role band so the
        # test suite's fixed-output expectations hold.
        temp = fallback_temp
    else:
        role_temp = temperature_for_role(step_name)
        temp = role_temp if role_temp is not None else fallback_temp

    return LLMCallOptions(
        step_name=step_name,
        temperature=temp,
        timeout_seconds=cap.default_timeout_seconds,
        max_tokens=cap.default_max_tokens,
        response_mode="json",
        provider_mode="auto",
    )


__all__ = [
    "ANALYST_TEMPERATURE",
    "EVALUATOR_TEMPERATURE",
    "LLMCallOptions",
    "PROVIDER_CAPABILITIES",
    "ProviderCapability",
    "WRITER_TEMPERATURE",
    "get_capability",
    "options_for_step",
    "temperature_for_role",
]
