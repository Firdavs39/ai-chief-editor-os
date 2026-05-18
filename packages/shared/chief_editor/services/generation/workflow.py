"""Workflow engine — advances a GenerationRun one step at a time.

Public surface:
- `advance_one_step(session, run) -> GenerationRun` — production worker
  entry point (NOT wired into the worker loop in Phase 2). Idempotent in
  spirit: terminal/cancelled runs return unchanged.
- `run_to_completion_for_tests(session, run, *, max_steps=20)` — TEST-ONLY
  helper. Production API routes MUST NOT use it.

Transactional contract (the Security Lead invariant):
- A failed run leaves zero PostCandidate rows. The candidate is created
  ONLY by `finalizer.finalize_candidate` after step 10 (quality_judge)
  succeeds. Step 11 (finalizer) is the only place in this package that
  imports `PostCandidate` and only as a type hint via models.
- Cancellation is checked BEFORE each LLM call. Mid-step requests
  complete, but no subsequent step runs.
- No ApprovalDecision or PublishJob is ever created here.

The workflow uses `provider.complete_json(system, user, schema, *,
temperature=...)` exactly as the existing call sites do. Phase 2 does NOT
extend the provider signature (per QUALITY_EDITORIAL_WORKFLOW_PLAN.md §1b
and §10b). Other LLMCallOptions fields are captured for logging only.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, select

from ...llm import get_llm_provider
from ...models import (
    GenerationArtifact,
    GenerationRun,
    GenerationStep,
    RawItem,
    StyleProfile,
    SystemLog,
    TrendCluster,
    TrendSignal,
)
from ...settings import get_settings
from ...time_utils import utcnow
from . import prompts
from .artifacts import get_run_artifacts_by_name, validate_payload
from .finalizer import finalize_candidate
from .provider_capabilities import options_for_step
from .steps import STEP_SEQUENCE, StepDef

log = logging.getLogger("chief_editor.generation.workflow")

_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_style(session: Session) -> StyleProfile | None:
    return session.exec(
        select(StyleProfile).where(StyleProfile.name == "default")
    ).first()


def _load_cluster(session: Session, run: GenerationRun) -> TrendCluster | None:
    if not run.cluster_id:
        return None
    return session.get(TrendCluster, run.cluster_id)


def _load_raw_items(
    session: Session, cluster: TrendCluster | None, limit: int = 5
) -> list[RawItem]:
    if cluster is None:
        return []
    return list(
        session.exec(
            select(RawItem)
            .join(TrendSignal, TrendSignal.raw_item_id == RawItem.id)
            .where(TrendSignal.cluster_id == cluster.id)
            .limit(limit)
        ).all()
    )


def _model_name_for(provider_name: str) -> str:
    s = get_settings()
    if provider_name == "anthropic":
        return s.anthropic_model
    if provider_name == "openai":
        return s.openai_model
    if provider_name == "ollama":
        return s.ollama_model
    return ""


def _audit_run_log(
    session: Session, event: str, *, run: GenerationRun, **extra: Any
) -> None:
    """Whitelisted SystemLog write. Allowed keys mirror the secrets router's
    `_audit`: run_id, status, step_count, duration_ms, error_class.

    Anything else is silently dropped. The vault secret-substring sweep
    tests cover this surface; this helper is the canonical entry point.
    """
    allowed = {"run_id", "status", "step_count", "duration_ms", "error_class"}
    data: dict[str, Any] = {"run_id": run.id, "status": run.status}
    data.update({k: v for k, v in extra.items() if k in allowed})
    session.add(SystemLog(level="info", event=event, message="", data=data))
    session.commit()


# ---------------------------------------------------------------------------
# User-prompt dispatch (different signature per step)
# ---------------------------------------------------------------------------


def _build_user_prompt(
    step_def: StepDef,
    *,
    cluster: TrendCluster | None,
    raw_items: list[RawItem],
    artifacts: dict[str, dict],
    style: StyleProfile | None,
) -> str:
    builder = step_def.user_builder_name
    if builder == "research_analyst":
        return prompts.user_research_analyst(cluster, raw_items)
    if builder == "trend_strategist":
        return prompts.user_trend_strategist(cluster, artifacts)
    if builder == "audience_psychology":
        return prompts.user_audience_psychology(artifacts, style)
    if builder == "style_dna_editor":
        return prompts.user_style_dna_editor(artifacts, style)
    if builder == "platform_writer_telegram":
        return prompts.user_platform_writer(artifacts, "Telegram", style=style)
    if builder == "platform_writer_threads":
        return prompts.user_platform_writer(artifacts, "Threads", style=style)
    if builder == "platform_writer_reddit":
        return prompts.user_platform_writer(artifacts, "Reddit", style=style)
    if builder == "critic_red_team":
        return prompts.user_critic_red_team(artifacts)
    if builder == "editor_in_chief_draft":
        return prompts.user_editor_in_chief_draft(artifacts)
    if builder == "quality_judge":
        return prompts.user_quality_judge(artifacts)
    raise RuntimeError(f"unknown user_builder_name '{builder}'")


# ---------------------------------------------------------------------------
# Step executors
# ---------------------------------------------------------------------------


def _execute_llm_step(
    session: Session, run: GenerationRun, step_def: StepDef
) -> dict[str, Any]:
    """Run one LLM step and return the validated artifact payload.

    The provider's `complete_json` is called with the documented signature
    (system, user, schema, temperature). LLMCallOptions provides the
    temperature; other options are deferred to Phase 3+ wiring.
    """
    provider = get_llm_provider()
    style = _load_style(session)
    cluster = _load_cluster(session, run)
    raw_items = _load_raw_items(session, cluster, limit=5)
    artifacts = get_run_artifacts_by_name(session, run)

    if step_def.system_builder is None or step_def.schema is None:
        raise RuntimeError(
            f"step {step_def.name} marked is_llm but missing prompt/schema"
        )
    system_prompt = step_def.system_builder(style)
    user_prompt = _build_user_prompt(
        step_def,
        cluster=cluster,
        raw_items=raw_items,
        artifacts=artifacts,
        style=style,
    )
    options = options_for_step(
        provider.name, step_def.name, is_judge=step_def.is_judge
    )

    raw_payload = provider.complete_json(
        system=system_prompt,
        user=user_prompt,
        schema=step_def.schema,
        temperature=options.temperature if options.temperature is not None else 0.7,
    )
    if not isinstance(raw_payload, dict):
        raise ValueError(
            f"provider returned non-dict payload for {step_def.name}: "
            f"{type(raw_payload).__name__}"
        )

    return validate_payload(step_def.artifact_name, raw_payload)


def _execute_finalizer_step(session: Session, run: GenerationRun) -> dict[str, Any]:
    """Backend assembly step. NO LLM call."""
    return finalize_candidate(session, run)


# ---------------------------------------------------------------------------
# Main advance entry point
# ---------------------------------------------------------------------------


def advance_one_step(session: Session, run: GenerationRun) -> GenerationRun:
    """Advance a GenerationRun by exactly one step. Commits per step.

    Behavior:
    - If `run.status` is terminal/cancelled: return immediately.
    - If `run.status == "queued"`: flip to "running", snapshot provider/model.
    - Create the next GenerationStep row with status="running".
    - Re-check `run.status` after the step row commit: a cancellation that
      landed between picks short-circuits BEFORE any LLM call.
    - Execute the step (LLM or finalizer).
    - On success: persist artifact, mark step succeeded, advance step_index.
      If this was the last step, mark run succeeded.
    - On any exception: mark step failed, mark run failed, truncate
      error_message to 240 chars. NO PostCandidate row is created.
    """
    session.refresh(run)
    if run.status in _TERMINAL_STATUSES:
        return run

    # Queued → running transition (one-time per run).
    if run.status == "queued":
        provider = get_llm_provider()
        run.status = "running"
        run.started_at = utcnow()
        run.provider = provider.name
        run.model = _model_name_for(provider.name)
        run.updated_at = utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        _audit_run_log(
            session,
            "generation.run.started",
            run=run,
            step_count=len(STEP_SEQUENCE),
        )

    idx = run.step_index
    if idx >= len(STEP_SEQUENCE):
        run.status = "succeeded"
        run.finished_at = utcnow()
        run.updated_at = utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    step_def = STEP_SEQUENCE[idx]
    started_at = utcnow()

    step = GenerationStep(
        run_id=run.id,
        step_index=idx,
        name=step_def.name,
        status="running",
        started_at=started_at,
    )
    session.add(step)
    session.commit()
    session.refresh(step)

    # Re-check cancellation — if a cancel came in between picks, short-circuit
    # BEFORE any LLM call. This is the cancellation hard rule.
    session.refresh(run)
    if run.status == "cancelled":
        step.status = "cancelled"
        step.finished_at = utcnow()
        step.updated_at = utcnow()
        session.add(step)
        session.commit()
        return run

    try:
        if step_def.is_llm:
            payload = _execute_llm_step(session, run, step_def)
        else:
            payload = _execute_finalizer_step(session, run)

        artifact = GenerationArtifact(
            run_id=run.id,
            step_id=step.id,
            name=step_def.artifact_name,
            schema_version="v1",
            payload=payload,
        )
        session.add(artifact)

        finished_at = utcnow()
        step.status = "succeeded"
        step.finished_at = finished_at
        step.duration_ms = int(
            (finished_at - started_at).total_seconds() * 1000
        )
        step.updated_at = finished_at

        run.step_index = idx + 1
        run.current_step = step_def.name
        run.updated_at = finished_at

        # Final step → mark run succeeded.
        if run.step_index >= len(STEP_SEQUENCE):
            run.status = "succeeded"
            run.finished_at = finished_at

        session.add(step)
        session.add(run)
        session.commit()
        session.refresh(run)

        if run.status == "succeeded":
            _audit_run_log(
                session,
                "generation.run.succeeded",
                run=run,
                step_count=run.step_index,
            )
        return run

    except Exception as exc:  # noqa: BLE001 — one terminal failure path
        msg = str(exc)[:240]
        finished_at = utcnow()
        step.status = "failed"
        step.finished_at = finished_at
        step.error_class = type(exc).__name__
        step.error_message = msg
        if started_at:
            step.duration_ms = int(
                (finished_at - started_at).total_seconds() * 1000
            )
        step.updated_at = finished_at

        run.status = "failed"
        run.error_class = step.error_class
        run.error_message = msg
        run.finished_at = finished_at
        run.updated_at = finished_at

        session.add(step)
        session.add(run)
        session.commit()
        session.refresh(run)

        log.warning(
            "generation.run.failed run_id=%s step=%s error_class=%s",
            run.id,
            step_def.name,
            step.error_class,
        )
        _audit_run_log(
            session,
            "generation.run.failed",
            run=run,
            error_class=step.error_class,
        )
        return run


# ---------------------------------------------------------------------------
# TEST-ONLY helper
# ---------------------------------------------------------------------------


def run_to_completion_for_tests(
    session: Session, run: GenerationRun, *, max_steps: int = 20
) -> GenerationRun:
    """TEST-ONLY: repeatedly call `advance_one_step` until terminal.

    DO NOT USE THIS FROM PRODUCTION API ROUTES OR WORKER LOOPS. The production
    worker loop (Phase 3+) calls `advance_one_step` once per tick and relies
    on its own scheduling so concurrency caps and cancellations work. This
    helper exists so end-to-end tests stay deterministic.
    """
    for _ in range(max_steps):
        session.refresh(run)
        if run.status in _TERMINAL_STATUSES:
            return run
        advance_one_step(session, run)
    session.refresh(run)
    if run.status not in _TERMINAL_STATUSES:
        raise RuntimeError(
            f"workflow did not terminate in {max_steps} steps "
            f"(status={run.status}, step_index={run.step_index})"
        )
    return run


__all__ = [
    "advance_one_step",
    "run_to_completion_for_tests",
]
