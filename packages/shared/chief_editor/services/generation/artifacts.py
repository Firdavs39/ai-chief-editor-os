"""Pydantic validators + DB persistence helpers for GenerationArtifacts.

Each step produces one artifact with a canonical name and a typed payload.
Validation guarantees:
- Schema-shaped output (catches LLM responses that don't match the prompt).
- Bounded `editorial_rationale` (≤ 1500 chars, user-safe). Phase 5.2 raised
  the limit from 240 — the original cap was UI-driven and forced the model
  into truncated reasoning, which caused Phase 5.1's failure on Kimi.
- Content-field limits match real platform API limits, not arbitrary numbers
  (TG body 4096 = Telegram Bot API, Threads body 500 = Threads platform,
  Reddit body 10000 = Reddit body soft cap, Reddit title 300 = Reddit hard
  limit). A draft that passes schema validation MUST be technically
  publishable on each platform.
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
    # `voice_brief` (the old style_dna_editor output) was DROPPED in the
    # role-refactor: per-channel voice now comes from the channel's
    # StyleProfile via workflow._load_style, so a separate LLM voice step
    # was a duplicate. VoiceBriefArtifact stays defined below for backward
    # compatibility of any external importer, but is no longer produced.
    "tg_post",
    "threads_post",
    "reddit_post",
    "critic_report",
    "final_brief",
    "fact_check",   # fact_checker output (information-asymmetric grounding)
    "quality_report",
    "candidate_link",  # finalizer's tiny artifact: {"candidate_id": "..."}
}

# ---------------------------------------------------------------------------
# Per-step pydantic models. Used for validation, not storage. We persist
# `model.model_dump()` (a dict) in GenerationArtifact.payload.
# ---------------------------------------------------------------------------


class _ArtifactBase(BaseModel):
    """Every step that needs an explanation includes editorial_rationale FIRST.

    Limit raised from 240 → 1500 in Phase 5.2 after the original cap caused
    Kimi to fail audience_psychology_analyst (the model wrote an honest
    multi-sentence rationale that exceeded 240 chars; the schema rejected it
    rather than the cap revealing a problem). 1500 is large enough for a
    short public editorial paragraph and small enough that hidden
    chain-of-thought won't fit.
    """

    editorial_rationale: str = Field(default="", max_length=1500)


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
    """DEPRECATED — output of the removed `style_dna_editor` step.

    Retained so external code that imports the symbol keeps working. The
    workflow no longer produces this artifact: per-channel voice is sourced
    from the channel's StyleProfile (see workflow._load_style /
    prompts._format_style). Do not add this back to STEP_SEQUENCE.
    """

    sentence_length_target: str
    vocab_lane: str
    must_avoid: list[str] = Field(default_factory=list, max_length=5)


class TelegramPostArtifact(_ArtifactBase):
    # 4096 = Telegram Bot API sendMessage limit. A draft that passes schema
    # MUST be publishable; shorter is editorially preferred (the critic / UI
    # advises on style), but the schema only enforces what's technically
    # sendable.
    body: str = Field(default="", max_length=4096)
    hook: str = Field(default="", max_length=160)
    cta: str = ""


class ThreadsPostArtifact(_ArtifactBase):
    # 500 = Threads platform character limit (hard).
    body: str = Field(default="", max_length=500)
    cta: str = ""


class RedditPostArtifact(_ArtifactBase):
    # 300 = Reddit title hard limit. 10000 = soft cap on Reddit selftext
    # (platform allows 40k but engagement collapses past ~10k).
    title: str = Field(default="", max_length=300)
    body: str = Field(default="", max_length=10000)
    cta: str = ""


class CriticReportArtifact(_ArtifactBase):
    slop_count: int = Field(default=0, ge=0)
    factual_concerns: list[str] = Field(default_factory=list, max_length=3)
    length_issues: list[str] = Field(default_factory=list, max_length=3)
    hook_grade: int = Field(default=5, ge=0, le=10)


class FactCheckArtifact(_ArtifactBase):
    """Output of the `fact_checker` step (information-asymmetric grounding).

    The fact_checker sees the FINAL assembled text + the research_brief's
    facts/sources, but NOT the writer's reasoning. It ties each checkable
    claim in the final draft to a source and surfaces the ones it cannot.

    - unsupported_claims: claims in the final text with no backing source
      (≤5). An empty list means every checkable claim is grounded.
    - grounding_score: 0..1 — fraction of checkable claims tied to a source.
    """

    unsupported_claims: list[str] = Field(default_factory=list, max_length=5)
    grounding_score: float = Field(default=1.0, ge=0.0, le=1.0)


class FinalBriefArtifact(_ArtifactBase):
    # Metadata fields (source_summary / why_it_matters / psychology_hook) are
    # operator-facing editorial commentary; their 400/300/200 caps were
    # over-tight. 1500-2000 chars = one screen in the UI card.
    # Content fields (final_*) match the per-platform artifact limits above
    # so the schema-vs-publish contract holds.
    topic: str
    source_summary: str = Field(default="", max_length=2000)
    why_it_matters: str = Field(default="", max_length=1500)
    psychology_hook: str = Field(default="", max_length=1500)
    final_tg: str = Field(default="", max_length=4096)
    final_threads: str = Field(default="", max_length=500)
    final_reddit: str = Field(default="", max_length=10000)
    cta: str = ""


class QualityReportArtifact(_ArtifactBase):
    style_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    viral_score: float = Field(default=0.0, ge=0.0, le=1.0)
    slop_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    controversy_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    # Scroll-stop / hook strength of the opening ~80 chars (0..1). Defaults
    # to 0.0 and is optional so older runs / providers that omit it still
    # validate; the judge prompt asks for it explicitly.
    hook_score: float = Field(default=0.0, ge=0.0, le=1.0)
    recommendation: Literal["approve", "revise", "reject"] = "revise"


class CandidateLinkArtifact(BaseModel):
    """Finalizer's tiny artifact — just records which PostCandidate was created."""

    candidate_id: str


ARTIFACT_MODELS: dict[str, type[BaseModel]] = {
    "research_brief": ResearchBriefArtifact,
    "angle": AngleArtifact,
    "psych": PsychArtifact,
    # voice_brief intentionally NOT mapped — step removed (see ARTIFACT_NAMES).
    "tg_post": TelegramPostArtifact,
    "threads_post": ThreadsPostArtifact,
    "reddit_post": RedditPostArtifact,
    "critic_report": CriticReportArtifact,
    "final_brief": FinalBriefArtifact,
    "fact_check": FactCheckArtifact,
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
    "FactCheckArtifact",
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
