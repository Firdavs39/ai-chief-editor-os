"""Quality Editorial Workflow — public surface.

Phase 1: enqueue_run() creates queued GenerationRun rows only.
Phase 2 (this commit): adds the workflow service layer:
  - workflow.py             — advance_one_step + run_to_completion_for_tests
  - steps.py                — STEP_SEQUENCE (11 steps)
  - prompts.py              — Russian-first prompts + JSON schemas
  - artifacts.py            — pydantic payload validators + DB helpers
  - finalizer.py            — assembles PostCandidate(status="draft") after
                              quality_judge succeeds (Step 11)
  - provider_capabilities.py — LLMCallOptions + per-provider metadata

Phase 2 does NOT wire the worker loop and does NOT change the FastAPI
router contract. The router still only enqueues; the workflow runs on
demand via `advance_one_step` (Phase 3 will plug the worker in).
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from ...models import (
    ChannelSource,
    GenerationRun,
    RawItem,
    SystemLog,
    TrendCluster,
    TrendSignal,
)
from ..channels import get_default_channel
from .steps import STEP_SEQUENCE, TOTAL_STEPS
from .workflow import advance_one_step, run_to_completion_for_tests

log = logging.getLogger("chief_editor.generation")


_VALID_REQUESTERS = {"api", "worker", "manual"}


def _top_cluster_ids_for_channel(
    session: Session, channel_id: str | None, top_n: int
) -> list[str]:
    """Top-N cluster ids by total_score, filtered to a channel's sources.

    When `channel_id` is None (no channel context at all), returns the global
    top-N — single-channel behaviour. When a channel is given, only clusters
    that have at least one signal originating from a raw item produced by one
    of the channel's linked sources are eligible. This keeps channel A's runs
    from being seeded by channel B's source pool.
    """
    if channel_id is None:
        rows = session.exec(
            select(TrendCluster)
            .order_by(TrendCluster.total_score.desc())
            .limit(top_n)
        ).all()
        return [c.id for c in rows]

    rows = session.exec(
        select(TrendCluster.id)
        .join(TrendSignal, TrendSignal.cluster_id == TrendCluster.id)
        .join(RawItem, RawItem.id == TrendSignal.raw_item_id)
        .join(ChannelSource, ChannelSource.source_id == RawItem.source_id)
        .where(ChannelSource.channel_id == channel_id)
        .group_by(TrendCluster.id)
        .order_by(TrendCluster.total_score.desc())
        .limit(top_n)
    ).all()
    return list(rows)


def enqueue_run(
    session: Session,
    *,
    cluster_id: str | None = None,
    top_n: int = 1,
    requested_by: str = "api",
    channel_id: str | None = None,
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
        channel_id: target channel for the run(s). When None, the default
            channel is resolved (so every run is channel-stamped once the
            migration has run). When `cluster_id` is None, the top-cluster
            selection is filtered to the channel's source pool.

    Returns:
        List of newly created GenerationRun rows (already committed).
    """
    if requested_by not in _VALID_REQUESTERS:
        requested_by = "api"

    top_n = max(1, min(int(top_n or 1), 10))

    # Resolve the channel: explicit > default. May still be None on a brand-new
    # deployment where the migration hasn't created a default channel yet; in
    # that case runs are created with channel_id=NULL and the workflow falls
    # back to single-channel behaviour.
    if channel_id is None:
        default_channel = get_default_channel(session)
        channel_id = default_channel.id if default_channel else None

    if cluster_id:
        cluster_ids: list[str | None] = [cluster_id]
    else:
        cluster_ids = list(
            _top_cluster_ids_for_channel(session, channel_id, top_n)
        )

    runs: list[GenerationRun] = []
    for cid in cluster_ids:
        run = GenerationRun(
            cluster_id=cid,
            channel_id=channel_id,
            requested_by=requested_by,
            status="queued",
            current_step="",
            step_index=0,
            total_steps=TOTAL_STEPS,
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


__all__ = [
    "STEP_SEQUENCE",
    "TOTAL_STEPS",
    "advance_one_step",
    "enqueue_run",
    "run_to_completion_for_tests",
]
