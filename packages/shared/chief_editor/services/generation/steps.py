"""STEP_SEQUENCE — the 11-step Quality Editorial Workflow.

Each `StepDef` is a pure-data descriptor of one workflow step. The workflow
engine (`workflow.py`) executes them in order. Steps 1-10 are LLM-driven;
step 11 (finalizer) is a backend assembly step that creates the
`PostCandidate(status="draft")` only after `final_brief` and
`quality_report` artifacts both exist.

This module imports prompts + artifact validators but performs NO DB writes
itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from . import prompts


@dataclass(frozen=True)
class StepDef:
    name: str
    artifact_name: str          # matches ARTIFACT_NAMES in artifacts.py
    is_llm: bool                # False for finalizer
    is_judge: bool              # True for quality_judge (lower temperature)
    schema: dict[str, Any] | None
    system_builder: Callable[..., str] | None
    user_builder_name: str      # dispatched by workflow.py (different signatures per step)


STEP_SEQUENCE: tuple[StepDef, ...] = (
    StepDef(
        name="research_analyst",
        artifact_name="research_brief",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_RESEARCH_BRIEF,
        system_builder=prompts.system_research_analyst,
        user_builder_name="research_analyst",
    ),
    StepDef(
        name="trend_strategist",
        artifact_name="angle",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_ANGLE,
        system_builder=prompts.system_trend_strategist,
        user_builder_name="trend_strategist",
    ),
    StepDef(
        name="audience_psychology_analyst",
        artifact_name="psych",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_PSYCH,
        system_builder=prompts.system_audience_psychology,
        user_builder_name="audience_psychology",
    ),
    StepDef(
        name="style_dna_editor",
        artifact_name="voice_brief",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_VOICE_BRIEF,
        system_builder=prompts.system_style_dna_editor,
        user_builder_name="style_dna_editor",
    ),
    StepDef(
        name="platform_writer_telegram",
        artifact_name="tg_post",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_TG_POST,
        system_builder=prompts.system_platform_writer_telegram,
        user_builder_name="platform_writer_telegram",
    ),
    StepDef(
        name="platform_writer_threads",
        artifact_name="threads_post",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_THREADS_POST,
        system_builder=prompts.system_platform_writer_threads,
        user_builder_name="platform_writer_threads",
    ),
    StepDef(
        name="platform_writer_reddit",
        artifact_name="reddit_post",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_REDDIT_POST,
        system_builder=prompts.system_platform_writer_reddit,
        user_builder_name="platform_writer_reddit",
    ),
    StepDef(
        name="critic_red_team",
        artifact_name="critic_report",
        is_llm=True,
        is_judge=True,           # critic uses lower temperature
        schema=prompts.SCHEMA_CRITIC_REPORT,
        system_builder=prompts.system_critic_red_team,
        user_builder_name="critic_red_team",
    ),
    StepDef(
        name="editor_in_chief_draft",
        artifact_name="final_brief",
        is_llm=True,
        is_judge=False,
        schema=prompts.SCHEMA_FINAL_BRIEF,
        system_builder=prompts.system_editor_in_chief_draft,
        user_builder_name="editor_in_chief_draft",
    ),
    StepDef(
        name="quality_judge",
        artifact_name="quality_report",
        is_llm=True,
        is_judge=True,
        schema=prompts.SCHEMA_QUALITY_REPORT,
        system_builder=prompts.system_quality_judge,
        user_builder_name="quality_judge",
    ),
    StepDef(
        name="finalizer",
        artifact_name="candidate_link",
        is_llm=False,             # backend-only assembly; no LLM call
        is_judge=False,
        schema=None,
        system_builder=None,
        user_builder_name="",
    ),
)


STEP_NAMES: tuple[str, ...] = tuple(s.name for s in STEP_SEQUENCE)
TOTAL_STEPS: int = len(STEP_SEQUENCE)  # 11


def get_step_by_index(index: int) -> StepDef:
    return STEP_SEQUENCE[index]


def get_step_by_name(name: str) -> StepDef | None:
    for s in STEP_SEQUENCE:
        if s.name == name:
            return s
    return None


__all__ = [
    "STEP_NAMES",
    "STEP_SEQUENCE",
    "StepDef",
    "TOTAL_STEPS",
    "get_step_by_index",
    "get_step_by_name",
]
