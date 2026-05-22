"""AI Chief Editor OS worker.

Three concurrent loops:
  1. Collector loop — periodically fetch new items per enabled source and recluster.
  2. Generation loop — generate candidates from top clusters lacking recent candidates.
  3. Publisher loop — dispatch pending publish jobs whose scheduled_at has passed.

The publisher loop is the third defense-in-depth gate: it re-validates that
each candidate has an approve decision before dispatching.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import timedelta

from sqlmodel import Session, select

from chief_editor.db import get_engine, init_db, session_scope
from chief_editor.models import (
    ApprovalDecision,
    GenerationRun,
    PostCandidate,
    PublishJob,
    PublishResult,
    Source,
    SystemLog,
    TrendCluster,
    WorkerHeartbeat,
)
from chief_editor.publishing import ApprovalRequiredError, get_publisher
from chief_editor.publishing.mock import MockPublisher
from chief_editor.services.candidate import generate_for_cluster
from chief_editor.services.dry_run import compute_payload
from chief_editor.services.generation import advance_one_step
from chief_editor.services.pipeline import recluster, run_collection_for_source
from chief_editor.settings import get_settings
from chief_editor.time_utils import utcnow

log = logging.getLogger("chief_editor.worker")

# Status set considered "in flight" — the generation_runs_loop picks runs in
# these states and advances them one step per tick. Terminal/cancelled runs
# are intentionally skipped (no auto-retry; user retry via UI is future work).
_GENERATION_PICKUP_STATUSES = ("queued", "running")
_GENERATION_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


def _heartbeat(session: Session, loop_name: str, event: str = "") -> None:
    """Upsert a worker heartbeat row. Called at the end of each loop tick."""
    hb = session.exec(
        select(WorkerHeartbeat).where(WorkerHeartbeat.loop_name == loop_name)
    ).first()
    now = utcnow()
    if hb is None:
        hb = WorkerHeartbeat(loop_name=loop_name, last_at=now, last_event=event, counter=1)
    else:
        hb.last_at = now
        hb.last_event = event
        hb.counter = (hb.counter or 0) + 1
        hb.updated_at = now
    session.add(hb)
    session.commit()


async def collector_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(30, settings.collect_interval_seconds)
    while not stop.is_set():
        try:
            with session_scope() as session:
                sources = list(
                    session.exec(select(Source).where(Source.enabled == True)).all()  # noqa: E712
                )
                inserted_total = 0
                for src in sources:
                    inserted_total += await run_collection_for_source(session, src)
                signals = recluster(session)
                session.add(
                    SystemLog(
                        level="info",
                        event="collector.tick",
                        message=f"ingested={inserted_total} new_signals={signals}",
                        data={"sources": len(sources), "inserted": inserted_total, "signals": signals},
                    )
                )
                session.commit()
                _heartbeat(session, "collector", event="collector.tick")
            log.info("collector tick complete")
        except Exception as exc:  # noqa: BLE001
            log.exception("collector loop error: %s", exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def generation_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(60, settings.generate_interval_seconds)
    while not stop.is_set():
        try:
            with session_scope() as session:
                # Phase Q TD-1 fix: skip the legacy single-shot generation
                # tick when a Phase 5.2+ workflow run is in flight. Both
                # paths call Kimi synchronously and share the worker
                # thread; running them concurrently blocks the workflow
                # for the duration of the legacy Kimi call (observed up
                # to 30 min in Phase Q v7 validation).
                active_run = session.exec(
                    select(GenerationRun).where(
                        GenerationRun.status.in_(["queued", "running"])  # type: ignore[attr-defined]
                    ).limit(1)
                ).first()
                if active_run is not None:
                    log.info(
                        "generation_loop skipped — Phase 5.2+ run %s "
                        "in flight (status=%s)",
                        active_run.id,
                        active_run.status,
                    )
                    _heartbeat(session, "generation", event="generator.skipped")
                else:
                    # find top clusters without a draft candidate in the last 24h
                    clusters = list(
                        session.exec(
                            select(TrendCluster)
                            .order_by(TrendCluster.total_score.desc())
                            .limit(5)
                        ).all()
                    )
                    generated = 0
                    fresh_cutoff = utcnow() - timedelta(hours=24)
                    for cluster in clusters:
                        recent = session.exec(
                            select(PostCandidate).where(
                                (PostCandidate.cluster_id == cluster.id)
                                & (PostCandidate.created_at >= fresh_cutoff)
                            )
                        ).first()
                        if recent is not None:
                            continue
                        generate_for_cluster(session, cluster)
                        generated += 1
                    if generated:
                        session.add(
                            SystemLog(
                                level="info",
                                event="generator.tick",
                                message=f"generated={generated}",
                                data={"generated": generated},
                            )
                        )
                        session.commit()
                    _heartbeat(session, "generation", event="generator.tick")
                    log.info("generation tick: %d new", generated)
        except Exception as exc:  # noqa: BLE001
            log.exception("generation loop error: %s", exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


# ---------------------------------------------------------------------------
# Quality Editorial Workflow — generation_runs_loop (Phase 3)
#
# Picks GenerationRun rows in "queued" / "running" state and advances each by
# exactly ONE step per tick via services.generation.advance_one_step. The
# workflow engine owns its own commits and the finalizer transaction; the
# worker just selects rows, advances them, and writes its heartbeat.
#
# Hard rules (Security Lead invariants):
#   - This loop NEVER creates ApprovalDecision rows.
#   - This loop NEVER creates PublishJob rows.
#   - This loop NEVER calls any Publisher.
#   - This loop NEVER touches DRY_RUN_PUBLISH or PUBLISHING_ENABLED.
#   - Failed runs are NOT auto-retried in Phase 3 (intentional; user-triggered
#     retry from the UI is future work).
#   - Cancelled runs are skipped (`status="cancelled"` excludes them from the
#     pick query; a defensive in-loop re-check handles races).
# ---------------------------------------------------------------------------


def _generation_runs_tick(session: Session, *, limit: int = 3) -> int:
    """One pass of the generation_runs loop. Returns count of runs advanced.

    Selects up to `limit` runs in queued/running state ordered by created_at,
    skips any that flipped to terminal between pick and advance, and calls
    `advance_one_step` once per run. Heartbeats at the end of the tick so
    the readiness UI sees the loop as fresh even when there is nothing to do.

    This function is exposed at module level so tests can drive a single
    tick deterministically without running the asyncio loop.
    """
    runs = list(
        session.exec(
            select(GenerationRun)
            .where(GenerationRun.status.in_(_GENERATION_PICKUP_STATUSES))  # type: ignore[attr-defined]
            .order_by(GenerationRun.created_at.asc())
            .limit(max(1, int(limit or 1)))
        ).all()
    )

    advanced = 0
    for run in runs:
        # Race guard — a cancel that lands between the SELECT and here MUST
        # short-circuit BEFORE any LLM call. `advance_one_step` does its own
        # refresh + cancellation check, but checking here as well keeps the
        # contract explicit at the worker boundary.
        session.refresh(run)
        if run.status in _GENERATION_TERMINAL_STATUSES:
            continue
        advance_one_step(session, run)
        advanced += 1

    _heartbeat(session, "generation_runs", event="generation_runs.tick")
    return advanced


async def generation_runs_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(15, settings.generate_interval_seconds // 8)
    while not stop.is_set():
        try:
            with session_scope() as session:
                advanced = _generation_runs_tick(session)
                if advanced:
                    log.info(
                        "generation_runs tick advanced %d run(s) (interval=%ds)",
                        advanced,
                        interval,
                    )
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            log.exception("generation_runs loop error: %s", exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


def _dispatch_one(session: Session, job: PublishJob) -> None:
    """Dispatch a single publish job with all safety gates enforced.

    Defense in depth — even if a `pending` job somehow reaches this point,
    every gate is re-checked here:
      1. Candidate exists.
      2. Approval decision exists and is `approve`.
      3. `PUBLISHING_ENABLED=true` (master kill switch).
      4. `DRY_RUN_PUBLISH=false` for real publish (else compute payload + done).
      5. Publisher's own `publish()` re-asserts approval at the boundary.
    """
    settings = get_settings()
    cand = session.get(PostCandidate, job.candidate_id)
    if cand is None:
        job.status = "failed"
        session.add(job)
        return

    approval = session.exec(
        select(ApprovalDecision).where(
            (ApprovalDecision.candidate_id == cand.id)
            & (ApprovalDecision.decision == "approve")
        )
    ).first()

    if approval is None:
        job.status = "failed"
        session.add(job)
        session.add(
            PublishResult(
                job_id=job.id,
                external_url="",
                success=False,
                error="no approval decision found",
                metrics_snapshot_at_publish={},
            )
        )
        return

    # Gate 1 — master switch off → never reach the wire.
    if not settings.publishing_enabled:
        job.status = "blocked"
        session.add(job)
        session.add(
            PublishResult(
                job_id=job.id,
                external_url="",
                success=False,
                error="PUBLISHING_ENABLED=false — real publish blocked",
                metrics_snapshot_at_publish={},
            )
        )
        session.add(
            SystemLog(
                level="warn",
                event="publisher.dispatch.blocked",
                message=f"Job {job.id} blocked by master switch.",
                data={"job_id": job.id, "reason": "publishing_disabled"},
            )
        )
        return

    # Gate 2 — dry-run mode → compute payload, mark done with dryrun:// URL.
    if settings.dry_run_publish:
        payload = compute_payload(cand, job.platform, scheduled_at=job.scheduled_at)
        job.status = "dry_run"
        session.add(job)
        session.add(
            PublishResult(
                job_id=job.id,
                external_url=f"dryrun://{job.platform}/{job.id}",
                success=True,
                error="",
                metrics_snapshot_at_publish={"dry_run": True, "preview": payload},
            )
        )
        session.add(
            SystemLog(
                level="info",
                event="publisher.dispatch",
                message=f"Dry-run dispatch for job {job.id} ({job.platform}).",
                data={
                    "job_id": job.id,
                    "platform": job.platform,
                    "dry_run": True,
                    "body_length": payload["body_length"],
                },
            )
        )
        # Candidate stays approved; do not mark as published.
        return

    # Real publish path.
    publisher = get_publisher(job.platform)
    # Honesty gate — if Live Mode is on but the resolved publisher is mock,
    # block instead of silently logging to console.
    if (
        settings.live_mode
        and isinstance(publisher, MockPublisher)
        and not settings.mock_mode
    ):
        job.status = "pending_config"
        session.add(job)
        session.add(
            PublishResult(
                job_id=job.id,
                external_url="",
                success=False,
                error=f"publisher for platform={job.platform} is not configured",
                metrics_snapshot_at_publish={},
            )
        )
        session.add(
            SystemLog(
                level="warn",
                event="publisher.dispatch.pending_config",
                message=f"Job {job.id} ({job.platform}) — publisher not configured.",
                data={"job_id": job.id, "platform": job.platform},
            )
        )
        return

    job.status = "running"
    session.add(job)
    session.commit()

    try:
        outcome = publisher.publish(job, cand, approval)
    except ApprovalRequiredError as exc:
        job.status = "failed"
        session.add(job)
        session.add(
            PublishResult(
                job_id=job.id,
                external_url="",
                success=False,
                error=f"approval gate: {exc}",
                metrics_snapshot_at_publish={},
            )
        )
        return

    job.status = "done" if outcome.success else "failed"
    if outcome.success:
        cand.status = "published"
        session.add(cand)
    session.add(job)
    session.add(
        PublishResult(
            job_id=job.id,
            external_url=outcome.external_url,
            success=outcome.success,
            error=outcome.error,
            metrics_snapshot_at_publish={},
        )
    )
    session.add(
        SystemLog(
            level="info",
            event="publisher.dispatch",
            message=f"Dispatched job {job.id} ({job.platform}) — success={outcome.success}.",
            data={
                "job_id": job.id,
                "platform": job.platform,
                "success": outcome.success,
                "external_url": outcome.external_url,
            },
        )
    )


async def publisher_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(5, settings.publish_interval_seconds)
    while not stop.is_set():
        try:
            with session_scope() as session:
                now = utcnow()
                due = list(
                    session.exec(
                        select(PublishJob)
                        .where(
                            (PublishJob.status == "pending")
                            & (PublishJob.scheduled_at <= now)
                        )
                        .order_by(PublishJob.scheduled_at.asc())
                        .limit(10)
                    ).all()
                )
                for job in due:
                    _dispatch_one(session, job)
                if due:
                    session.commit()
                    log.info("publisher dispatched %d jobs", len(due))
                _heartbeat(session, "publisher", event="publisher.tick")
        except Exception as exc:  # noqa: BLE001
            log.exception("publisher loop error: %s", exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue


async def _main() -> None:
    # Structured logging — JSON in prod, console in dev. Redacts known secrets.
    try:
        from chief_editor.logging_config import configure_logging

        configure_logging(service="worker")
    except Exception:  # noqa: BLE001 — fall back to stdlib logging if structlog setup fails
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    init_db()
    settings = get_settings()
    log.info(
        "worker up. env=%s mock=%s live=%s dry_run=%s publishing=%s llm=%s interval=(c=%ds, g=%ds, p=%ds)",
        settings.app_env,
        settings.mock_mode,
        settings.live_mode,
        settings.dry_run_publish,
        settings.publishing_enabled,
        settings.llm_provider,
        settings.collect_interval_seconds,
        settings.generate_interval_seconds,
        settings.publish_interval_seconds,
    )

    # Eager heartbeats — write one row per loop on startup so /worker/status
    # flips to `running` within a second of boot, before the first slow tick.
    try:
        with session_scope() as boot_session:
            for loop_name in ("collector", "generation", "publisher", "generation_runs"):
                _heartbeat(boot_session, loop_name, event="worker.boot")
    except Exception as exc:  # noqa: BLE001
        log.warning("worker initial heartbeat failed: %s", exc)

    stop = asyncio.Event()

    def _signal_handler(*_: object) -> None:
        log.info("worker stop requested")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig_name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows asyncio doesn't support add_signal_handler — rely on KeyboardInterrupt
            signal.signal(sig, _signal_handler)

    await asyncio.gather(
        collector_loop(stop),
        generation_loop(stop),
        publisher_loop(stop),
        generation_runs_loop(stop),
    )

    get_engine().dispose()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        log.info("worker interrupted")


if __name__ == "__main__":
    main()
