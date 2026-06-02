"""STEP_SEQUENCE — the 11-step Quality Editorial Workflow.

Each `StepDef` is a pure-data descriptor of one workflow step. The workflow
engine (`workflow.py`) executes them in order. Steps 1-10 are LLM-driven;
step 11 (finalizer) is a backend assembly step that creates the
`PostCandidate(status="draft")` only after `final_brief` and
`quality_report` artifacts both exist.

Role refactor (audit, May 2026):
- DROPPED `style_dna_editor` — per-channel voice now comes from the
  channel's StyleProfile (workflow._load_style), so a separate LLM voice
  step (`voice_brief`) was a duplicate.
- ADDED `fact_checker` AFTER `editor_in_chief_draft` and BEFORE
  `quality_judge`: the editor assembles the final text, the fact_checker
  grounds the FINAL claims against the research facts (with information
  asymmetry — it does not see the writer's reasoning), then the judge
  scores the grounded result.
- Net step count is unchanged at 11 (10 LLM + finalizer): −style_dna,
  +fact_checker.

This module imports prompts + artifact validators but performs NO DB writes
itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import prompts
from .provider_capabilities import temperature_for_role


@dataclass(frozen=True)
class StepDef:
    name: str
    artifact_name: str          # matches ARTIFACT_NAMES in artifacts.py
    is_llm: bool                # False for finalizer
    is_judge: bool              # True for evaluator roles (lower temperature)
    schema: dict[str, Any] | None
    system_builder: Callable[..., str] | None
    user_builder_name: str      # dispatched by workflow.py (different signatures per step)
    # Per-role temperature band (writer 0.6 / evaluator 0.2 / analyst 0.3),
    # resolved once from provider_capabilities so STEP_SEQUENCE stays the
    # single source of truth for "what temperature does this role want".
    # The workflow forwards this for real providers; the mock provider
    # overrides to its deterministic 0.0 (see provider_capabilities).
    role_temperature: float | None = None
    # Platform-scoped generation: the outbound platform this step writes for
    # ("telegram" / "threads" / "reddit"). None for every non-writer step
    # (analysts, critic, editor, fact_checker, judge, finalizer — they are
    # platform-agnostic). When a run targets a single-platform channel, the
    # workflow SKIPS writer steps whose `platform` is not in the channel's
    # target set (no LLM call). STEP_SEQUENCE stays the single source of
    # truth for "which platform does this writer serve", mirroring the
    # `role_temperature` pattern above. The step COUNT never changes — a
    # skipped writer is a no-op step, not a deleted one.
    platform: str | None = None


STEP_SEQUENCE: tuple[StepDef, ...] = (
    StepDef(
        name="research_analyst",
        artifact_name="research_brief",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_RESEARCH_BRIEF,
        system_builder=prompts.system_research_analyst,
        user_builder_name="research_analyst",
        role_temperature=temperature_for_role("research_analyst"),
    ),
    StepDef(
        name="trend_strategist",
        artifact_name="angle",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_ANGLE,
        system_builder=prompts.system_trend_strategist,
        user_builder_name="trend_strategist",
        role_temperature=temperature_for_role("trend_strategist"),
    ),
    StepDef(
        name="audience_psychology_analyst",
        artifact_name="psych",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_PSYCH,
        system_builder=prompts.system_audience_psychology,
        user_builder_name="audience_psychology",
        role_temperature=temperature_for_role("audience_psychology_analyst"),
    ),
    StepDef(
        name="platform_writer_telegram",
        artifact_name="tg_post",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_TG_POST,
        system_builder=prompts.system_platform_writer_telegram,
        user_builder_name="platform_writer_telegram",
        role_temperature=temperature_for_role("platform_writer_telegram"),
        platform="telegram",
    ),
    StepDef(
        name="platform_writer_threads",
        artifact_name="threads_post",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_THREADS_POST,
        system_builder=prompts.system_platform_writer_threads,
        user_builder_name="platform_writer_threads",
        role_temperature=temperature_for_role("platform_writer_threads"),
        platform="threads",
    ),
    StepDef(
        name="platform_writer_reddit",
        artifact_name="reddit_post",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_REDDIT_POST,
        system_builder=prompts.system_platform_writer_reddit,
        user_builder_name="platform_writer_reddit",
        role_temperature=temperature_for_role("platform_writer_reddit"),
        platform="reddit",
    ),
    StepDef(
        name="critic_red_team",
        artifact_name="critic_report",
        is_llm=True,
        is_judge=True,           # evaluator — lower temperature
        schema=prompts.SCHEMA_CRITIC_REPORT,
        system_builder=prompts.system_critic_red_team,
        user_builder_name="critic_red_team",
        role_temperature=temperature_for_role("critic_red_team"),
    ),
    StepDef(
        name="editor_in_chief_draft",
        artifact_name="final_brief",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_FINAL_BRIEF,
        system_builder=prompts.system_editor_in_chief_draft,
        user_builder_name="editor_in_chief_draft",
        role_temperature=temperature_for_role("editor_in_chief_draft"),
    ),
    # fact_checker runs AFTER the editor assembles the final text: it grounds
    # the FINAL claims against research facts before the judge scores them.
    StepDef(
        name="fact_checker",
        artifact_name="fact_check",
        is_llm=True,
        is_judge=True,           # evaluator — lower temperature
        schema=prompts.SCHEMA_FACT_CHECK,
        system_builder=prompts.system_fact_checker,
        user_builder_name="fact_checker",
        role_temperature=temperature_for_role("fact_checker"),
    ),
    StepDef(
        name="quality_judge",
        artifact_name="quality_report",
        is_llm=True,
        is_judge=True,
        schema=prompts.SCHEMA_QUALITY_REPORT,
        system_builder=prompts.system_quality_judge,
        user_builder_name="quality_judge",
        role_temperature=temperature_for_role("quality_judge"),
    ),
    StepDef(
        name="finalizer",
        artifact_name="candidate_link",
        is_llm=False,             # backend-only assembly; no LLM call
        is_judge=False,
        schema=None,
        system_builder=None,
        user_builder_name="",
        role_temperature=None,
    ),
)


STEP_NAMES: tuple[str, ...] = tuple(s.name for s in STEP_SEQUENCE)
TOTAL_STEPS: int = len(STEP_SEQUENCE)  # 11 (10 LLM + finalizer)

# The set of outbound platforms that have a dedicated writer step. A run that
# targets a channel whose platform is in this set is eligible for
# platform-scoped generation (writers for other platforms are skipped). A
# channel platform NOT in this set (unknown/future) disables scoping and runs
# every writer — the documented legacy/unrecognized fallback.
WRITER_PLATFORMS: frozenset[str] = frozenset(
    s.platform for s in STEP_SEQUENCE if s.platform is not None
)


def get_step_by_index(index: int) -> StepDef:
    return STEP_SEQUENCE[index]


def get_step_by_name(name: str) -> StepDef | None:
    for s in STEP_SEQUENCE:
        if s.name == name:
            return s
    return None


def platform_for_step(name: str) -> str | None:
    """Outbound platform a step writes for, or None for platform-agnostic steps."""
    step = get_step_by_name(name)
    return step.platform if step is not None else None


__all__ = [
    "STEP_NAMES",
    "STEP_SEQUENCE",
    "StepDef",
    "TOTAL_STEPS",
    "WRITER_PLATFORMS",
    "get_step_by_index",
    "get_step_by_name",
    "platform_for_step",
]
