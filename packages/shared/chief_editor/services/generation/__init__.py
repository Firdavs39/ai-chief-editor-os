"""Quality Editorial Workflow — service skeleton (Phase 1).

This phase ONLY enqueues `GenerationRun` rows. No worker execution. No LLM
calls. No artifacts. No `PostCandidate` creation. The router uses this
function so the implementation stays in one place.

Subsequent phases will add:
  - workflow.py     — per-step orchestration
  - steps.py        — STEP_SEQUENCE definitions
  - prompts.py      — Russian-first prompts + JSON schemas
  - artifacts.py    — payload validators
  - finalizer.py    — assembles PostCandidate after Step 8 succeeds
  - provider_capabilities.py — per-provider call options

All of those land behind the same enqueue_run() public surface so the
router and tests don't change shape.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from ...models import GenerationRun, SystemLog, TrendCluster

log = logging.getLogger("chief_editor.generation")


_VALID_REQUESTERS = {"api", "worker", "manual"}


def enqueue_run(
    session: Session,
    *,
    cluster_id: str | None = None,
    top_n: int = 1,
    requested_by: str = "api",
) -> list[GenerationRun]:
    """Create one or more queued `GenerationRun` rows. No LLM call.

    Args:
        session: an open SQLModel Session.
        cluster_id: if provided, enqueue exactly one run for that cluster.
            Caller is responsible for verifying the cluster exists; this
            function will still create the run row even if not — the worker
            (Phase 2+) will mark it failed at pickup.
        top_n: when cluster_id is None, enqueue runs for the top-N clusters
            by `total_score` descending. Capped at 10 in this phase to keep
            queue depth manageable.
        requested_by: one of {"api", "worker", "manual"}. Anything else
            is coerced to "api".

    Returns:
        List of newly created GenerationRun rows (already committed).
    """
    if requested_by not in _VALID_REQUESTERS:
        requested_by = "api"

    top_n = max(1, min(int(top_n or 1), 10))

    if cluster_id:
        cluster_ids: list[str | None] = [cluster_id]
    else:
        clusters = list(
            session.exec(
                select(TrendCluster)
                .order_by(TrendCluster.total_score.desc())
                .limit(top_n)
            ).all()
        )
        cluster_ids = [c.id for c in clusters]

    runs: list[GenerationRun] = []
    for cid in cluster_ids:
        run = GenerationRun(
            cluster_id=cid,
            requested_by=requested_by,
            status="queued",
            current_step="",
            step_index=0,
            total_steps=8,
        )
        session.add(run)
        runs.append(run)

    if not runs:
        return []

    session.commit()
    for run in runs:
        session.refresh(run)

    # Audit one SystemLog row per enqueued run. Whitelist-only data payload —
    # mirrors the discipline at apps/api/app/routers/secrets.py::_audit.
    # Allowed keys for generation events: run_id, status, step_count,
    # duration_ms, error_class. Nothing else.
    for run in runs:
        session.add(
            SystemLog(
                level="info",
                event="generation.run.queued",
                message="",
                data={
                    "run_id": run.id,
                    "status": run.status,
                    "step_count": run.total_steps,
                },
            )
        )
    session.commit()

    log.info(
        "generation.run.queued count=%d requested_by=%s",
        len(runs),
        requested_by,
    )
    return runs


__all__ = ["enqueue_run"]
