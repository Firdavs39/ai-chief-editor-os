"""Finalizer — Step 11 of the Quality Editorial Workflow.

Backend-only step (NO LLM call). Runs after `quality_judge` has succeeded
and the run has both `final_brief` and `quality_report` artifacts. Assembles
the canonical `PostCandidate(status="draft")` row, runs the existing
deterministic `chief_editor.services.critic.critique()` heuristic over the
final fields, and links the run to the candidate via `run.candidate_id`.

This is the **only** place in the entire `services/generation/` package
that creates a `PostCandidate`. The Security Lead invariant:

    grep -r "PostCandidate(" packages/shared/chief_editor/services/generation/
        → exactly one hit, inside this file.

NEVER creates `ApprovalDecision` or `PublishJob`. NEVER publishes.
"""

from __future__ import annotations

import logging

from sqlmodel import Session

from ...models import GenerationRun, PostCandidate
from ...time_utils import utcnow
from ..critic import critique
from .artifacts import get_run_artifacts_by_name

log = logging.getLogger("chief_editor.generation.finalizer")


class FinalizerError(RuntimeError):
    """Raised when prerequisites for finalization are missing."""


def finalize_candidate(session: Session, run: GenerationRun) -> dict:
    """Create the draft PostCandidate for this run.

    Returns the artifact payload `{"candidate_id": <new candidate id>}`.
    Raises FinalizerError if either required prior artifact is missing.

    Safety:
    - candidate.status is hard-coded to "draft". No other status is reachable
      from this code path.
    - No ApprovalDecision or PublishJob is created here or anywhere in the
      generation pipeline.
    - The heuristic `critique()` runs over the assembled fields and the
      output is stored as `critic_notes`, mirroring the legacy
      `services/candidate.py::generate_for_cluster` shape so existing
      Editor UI keeps working.
    """
    artifacts = get_run_artifacts_by_name(session, run)

    final_brief = artifacts.get("final_brief")
    quality_report = artifacts.get("quality_report")
    if not final_brief:
        raise FinalizerError(
            "finalizer requires final_brief artifact (from editor_in_chief_draft step)"
        )
    if not quality_report:
        raise FinalizerError(
            "finalizer requires quality_report artifact (from quality_judge step)"
        )

    notes = critique(
        tg_version=str(final_brief.get("final_tg", "")),
        threads_version=str(final_brief.get("final_threads", "")),
        cta=str(final_brief.get("cta", "")),
        source_summary=str(final_brief.get("source_summary", "")),
        psychology_hook=str(final_brief.get("psychology_hook", "")),
        controversy_keywords_hits=int(
            round(float(quality_report.get("controversy_risk", 0.0)) * 4)
        ),
    )

    candidate = PostCandidate(
        cluster_id=run.cluster_id,
        topic=str(final_brief.get("topic", "")),
        source_summary=str(final_brief.get("source_summary", "")),
        why_it_matters=str(final_brief.get("why_it_matters", "")),
        psychology_hook=str(final_brief.get("psychology_hook", "")),
        tg_version=str(final_brief.get("final_tg", "")),
        threads_version=str(final_brief.get("final_threads", "")),
        reddit_version=str(final_brief.get("final_reddit", "")),
        cta=str(final_brief.get("cta", "")),
        style_match_score=float(quality_report.get("style_match_score", 0.7)),
        viral_score=float(quality_report.get("viral_score", 0.6)),
        slop_risk=float(quality_report.get("slop_risk", 0.2)),
        controversy_risk=float(quality_report.get("controversy_risk", 0.1)),
        recommendation=str(quality_report.get("recommendation", "revise")),
        critic_notes=notes,
        status="draft",   # invariant — no other status is reachable here
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)

    # Link the run to the candidate. The workflow engine commits this on
    # successful step completion alongside the GenerationArtifact row.
    run.candidate_id = candidate.id
    run.updated_at = utcnow()
    session.add(run)
    session.commit()
    session.refresh(run)

    log.info(
        "generation.finalizer.candidate_created run_id=%s candidate_id=%s status=%s",
        run.id,
        candidate.id,
        candidate.status,
    )
    return {"candidate_id": candidate.id}


__all__ = ["FinalizerError", "finalize_candidate"]
