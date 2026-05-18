"""Pydantic validators + DB persistence helpers for GenerationArtifacts.

Each step produces one artifact with a canonical name and a typed payload.
Validation guarantees:
- Schema-shaped output (catches LLM responses that don't match the prompt).
- Bounded `editorial_rationale` (≤ 240 chars, user-safe).
- NO raw model text / prompts / completions are persisted — only the parsed
  pydantic dump of the validated payload reaches the DB.

These validators are NOT the LLMProvider's parser — they run AFTER the
provider returns parsed JSON and BEFORE we save the artifact row.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ...models import GenerationArtifact, GenerationRun

# ---------------------------------------------------------------------------
# Artifact name registry (single source of truth)
# ---------------------------------------------------------------------------

ARTIFACT_NAMES = {
    "research_brief",
    "angle",
    "psych",
    "voice_brief",
    "tg_post",
    "threads_post",
    "reddit_post",
    "critic_report",
    "final_brief",
    "quality_report",
    "candidate_link",  # finalizer's tiny artifact: {"candidate_id": "..."}
}

# ---------------------------------------------------------------------------
# Per-step pydantic models. Used for validation, not storage. We persist
# `model.model_dump()` (a dict) in GenerationArtifact.payload.
# ---------------------------------------------------------------------------


class _ArtifactBase(BaseModel):
    """Every step that needs an explanation includes editorial_rationale FIRST."""

    editorial_rationale: str = Field(default="", max_length=240)


class ResearchBriefArtifact(_ArtifactBase):
    fact_bullets: list[str] = Field(default_factory=list, min_length=3, max_length=7)
    source_handles: list[str] = Field(default_factory=list, max_length=5)
    gaps: list[str] = Field(default_factory=list, max_length=3)


class AngleArtifact(_ArtifactBase):
    primary_angle: str
    contrarian_take: str = ""
    why_now: str = ""


class PsychArtifact(_ArtifactBase):
    target_emotion: str
    hook_pattern: str
    cognitive_bias_lever: str


class VoiceBriefArtifact(_ArtifactBase):
    sentence_length_target: str
    vocab_lane: str
    must_avoid: list[str] = Field(default_factory=list, max_length=5)


class TelegramPostArtifact(_ArtifactBase):
    body: str = Field(default="", max_length=1024)
    hook: str = Field(default="", max_length=80)
    cta: str = ""


class ThreadsPostArtifact(_ArtifactBase):
    body: str = Field(default="", max_length=500)
    cta: str = ""


class RedditPostArtifact(_ArtifactBase):
    title: str = Field(default="", max_length=300)
    body: str = Field(default="", max_length=1500)
    cta: str = ""


class CriticReportArtifact(_ArtifactBase):
    slop_count: int = Field(default=0, ge=0)
    factual_concerns: list[str] = Field(default_factory=list, max_length=3)
    length_issues: list[str] = Field(default_factory=list, max_length=3)
    hook_grade: int = Field(default=5, ge=0, le=10)


class FinalBriefArtifact(_ArtifactBase):
    topic: str
    source_summary: str = Field(default="", max_length=400)
    why_it_matters: str = Field(default="", max_length=300)
    psychology_hook: str = Field(default="", max_length=200)
    final_tg: str = Field(default="", max_length=1024)
    final_threads: str = Field(default="", max_length=500)
    final_reddit: str = Field(default="", max_length=1500)
    cta: str = ""


class QualityReportArtifact(_ArtifactBase):
    style_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    viral_score: float = Field(default=0.0, ge=0.0, le=1.0)
    slop_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    controversy_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    recommendation: Literal["approve", "revise", "reject"] = "revise"


class CandidateLinkArtifact(BaseModel):
    """Finalizer's tiny artifact — just records which PostCandidate was created."""

    candidate_id: str


ARTIFACT_MODELS: dict[str, type[BaseModel]] = {
    "research_brief": ResearchBriefArtifact,
    "angle": AngleArtifact,
    "psych": PsychArtifact,
    "voice_brief": VoiceBriefArtifact,
    "tg_post": TelegramPostArtifact,
    "threads_post": ThreadsPostArtifact,
    "reddit_post": RedditPostArtifact,
    "critic_report": CriticReportArtifact,
    "final_brief": FinalBriefArtifact,
    "quality_report": QualityReportArtifact,
    "candidate_link": CandidateLinkArtifact,
}


def validate_payload(artifact_name: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Validate a raw provider payload against the step's artifact model.

    Raises pydantic.ValidationError on shape mismatch — the workflow engine
    catches this and marks the step as failed with the truncated error
    message. NO raw model text reaches the DB.
    """
    model = ARTIFACT_MODELS.get(artifact_name)
    if model is None:
        raise ValueError(f"unknown artifact name '{artifact_name}'")
    obj = model.model_validate(raw)
    return obj.model_dump(mode="json")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def get_run_artifacts_by_name(
    session: Session, run: GenerationRun
) -> dict[str, dict[str, Any]]:
    """Return all artifacts for a run keyed by their canonical name."""
    rows = list(
        session.exec(
            select(GenerationArtifact)
            .where(GenerationArtifact.run_id == run.id)
            .order_by(GenerationArtifact.created_at.asc())
        ).all()
    )
    out: dict[str, dict[str, Any]] = {}
    for a in rows:
        out[a.name] = dict(a.payload or {})
    return out


__all__ = [
    "ARTIFACT_MODELS",
    "ARTIFACT_NAMES",
    "AngleArtifact",
    "CandidateLinkArtifact",
    "CriticReportArtifact",
    "FinalBriefArtifact",
    "PsychArtifact",
    "QualityReportArtifact",
    "RedditPostArtifact",
    "ResearchBriefArtifact",
    "TelegramPostArtifact",
    "ThreadsPostArtifact",
    "VoiceBriefArtifact",
    "get_run_artifacts_by_name",
    "validate_payload",
]
