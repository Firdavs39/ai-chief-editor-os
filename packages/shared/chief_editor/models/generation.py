"""GenerationRun / GenerationStep / GenerationArtifact — Quality Editorial Workflow.

Phase 1: data model only. No worker execution wired here.

Invariants enforced by code structure (not by DB constraints):
- A `GenerationRun` flows queued → running → succeeded | failed | cancelled.
- `candidate_id` is set ONLY by the finalizer service after Step 8 (Quality
  Judge) succeeds. The router and the worker never write it directly.
- `GenerationArtifact.payload` stores only the canonical JSON output of a
  step. Never raw model text. Never private chain-of-thought.
- All `error_message` fields are truncated to 240 characters at the call
  site (mirrors `readiness/checks.py::_safe_error`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from ._base import TimestampedBase, json_column


class GenerationRun(TimestampedBase, table=True):
    __tablename__ = "generation_runs"

    cluster_id: str | None = Field(
        default=None, foreign_key="trend_clusters.id", index=True
    )
    requested_by: str = Field(default="api", max_length=32)
    # api | worker | manual

    status: str = Field(default="queued", index=True, max_length=24)
    # queued | running | succeeded | failed | cancelled

    current_step: str = Field(default="", max_length=48)
    step_index: int = 0
    total_steps: int = 8

    # Filled ONLY by finalizer.py after Step 8 succeeds. Phase 1 never writes
    # this column.
    candidate_id: str | None = Field(
        default=None, foreign_key="post_candidates.id", index=True
    )

    error_class: str = Field(default="", max_length=64)
    error_message: str = Field(default="", max_length=240)

    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)

    provider: str = Field(default="", max_length=24)
    model: str = Field(default="", max_length=64)


class GenerationStep(TimestampedBase, table=True):
    __tablename__ = "generation_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "step_index", name="uq_generation_run_step_index"),
    )

    run_id: str = Field(foreign_key="generation_runs.id", index=True)
    step_index: int

    name: str = Field(index=True, max_length=48)
    # research_analyst | trend_strategist | audience_psychology_analyst |
    # style_dna_editor | platform_writer_telegram | platform_writer_threads |
    # platform_writer_reddit | critic_red_team | editor_in_chief_finalizer |
    # quality_judge

    status: str = Field(default="pending", max_length=24)
    # pending | running | succeeded | failed | skipped | cancelled

    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    duration_ms: int | None = Field(default=None)

    tokens_in: int | None = Field(default=None)
    tokens_out: int | None = Field(default=None)

    error_class: str = Field(default="", max_length=64)
    error_message: str = Field(default="", max_length=240)


class GenerationArtifact(TimestampedBase, table=True):
    __tablename__ = "generation_artifacts"

    run_id: str = Field(foreign_key="generation_runs.id", index=True)
    step_id: str = Field(foreign_key="generation_steps.id", index=True)

    name: str = Field(max_length=48)
    # research_brief | angle | psych | voice_brief | tg_post | threads_post |
    # reddit_post | critic_report | final_brief | quality_report

    schema_version: str = Field(default="v1", max_length=12)

    # Canonical step output JSON. Storage contract:
    # - Only fields defined by the step's prompt schema.
    # - May include an `editorial_rationale` field (<= 240 chars, user-safe).
    # - MUST NOT include raw model text, hidden chain-of-thought, or
    #   private reasoning beyond the bounded `editorial_rationale`.
    payload: dict[str, Any] = Field(
        default_factory=dict, sa_column=json_column()
    )
