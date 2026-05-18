"""Phase 3 — worker wiring for the Quality Editorial Workflow.

Tests drive the synchronous tick helper `_generation_runs_tick` directly
(no asyncio) so they stay deterministic and have zero live network calls.
"""

from __future__ import annotations

from sqlmodel import select

from chief_editor.models import (
    ApprovalDecision,
    GenerationArtifact,
    GenerationRun,
    GenerationStep,
    PostCandidate,
    PublishJob,
    TrendCluster,
    WorkerHeartbeat,
)
from chief_editor.services.generation import enqueue_run
from worker.main import (
    _GENERATION_PICKUP_STATUSES,
    _GENERATION_TERMINAL_STATUSES,
    _generation_runs_tick,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed(client) -> None:
    client.post("/demo/seed")


def _make_queued_run(session) -> GenerationRun:
    cluster = session.exec(select(TrendCluster)).first()
    cluster_id = cluster.id if cluster else None
    runs = enqueue_run(
        session, cluster_id=cluster_id, top_n=1, requested_by="manual"
    )
    return runs[0]


# ---------------------------------------------------------------------------
# Constants exposed for tests / observability
# ---------------------------------------------------------------------------


def test_pickup_and_terminal_statuses_are_disjoint() -> None:
    """Sanity: a run cannot be both pickable and terminal."""
    assert set(_GENERATION_PICKUP_STATUSES).isdisjoint(_GENERATION_TERMINAL_STATUSES)
    assert _GENERATION_PICKUP_STATUSES == ("queued", "running")
    assert frozenset(
        {"succeeded", "failed", "cancelled"}
    ) == _GENERATION_TERMINAL_STATUSES


# ---------------------------------------------------------------------------
# Tick advances queued / running runs
# ---------------------------------------------------------------------------


def test_tick_advances_queued_run_by_one_step(client, session) -> None:
    _seed(client)
    run = _make_queued_run(session)
    assert run.status == "queued"
    assert run.step_index == 0

    advanced = _generation_runs_tick(session)

    assert advanced == 1
    session.refresh(run)
    assert run.status == "running"
    assert run.step_index == 1
    assert run.current_step == "research_analyst"

    steps = list(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    )
    assert len(steps) == 1
    assert steps[0].status == "succeeded"
    assert steps[0].name == "research_analyst"


def test_tick_continues_running_run_with_next_step(client, session) -> None:
    _seed(client)
    run = _make_queued_run(session)
    _generation_runs_tick(session)
    session.refresh(run)
    assert run.step_index == 1

    _generation_runs_tick(session)
    session.refresh(run)
    assert run.step_index == 2
    assert run.current_step == "trend_strategist"


def test_tick_processes_runs_in_created_at_order(client, session) -> None:
    _seed(client)
    r1 = _make_queued_run(session)
    r2 = _make_queued_run(session)
    # r1 was created first; tick should advance both (limit=3), and r1 should
    # have step row before r2.
    _generation_runs_tick(session)
    s1 = list(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == r1.id)
        ).all()
    )
    s2 = list(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == r2.id)
        ).all()
    )
    assert len(s1) == 1
    assert len(s2) == 1
    assert s1[0].created_at <= s2[0].created_at


def test_tick_respects_limit(client, session) -> None:
    """When more than `limit` runs are queued, only `limit` are advanced
    in a single tick. The rest stay queued."""
    _seed(client)
    runs = [_make_queued_run(session) for _ in range(5)]
    advanced = _generation_runs_tick(session, limit=2)
    assert advanced == 2
    # Re-read all runs; first two should be running, rest queued.
    for r in runs:
        session.refresh(r)
    advanced_count = sum(1 for r in runs if r.status == "running")
    queued_count = sum(1 for r in runs if r.status == "queued")
    assert advanced_count == 2
    assert queued_count == 3


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_tick_skips_cancelled_runs_and_never_calls_llm(
    client, session, monkeypatch
) -> None:
    from chief_editor.llm import registry as reg

    _seed(client)
    run = _make_queued_run(session)
    run.status = "cancelled"
    session.add(run)
    session.commit()

    # Tripwire: any LLM call on a cancelled run is an immediate failure.
    provider = reg.get_llm_provider()

    def _boom(*args, **kwargs):
        raise AssertionError("LLM was called for a cancelled run")

    monkeypatch.setattr(provider, "complete_json", _boom)

    advanced = _generation_runs_tick(session)
    assert advanced == 0

    # No step row should exist for a cancelled-at-pickup run.
    steps = list(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    )
    assert steps == []


def test_cancel_between_pick_and_advance_short_circuits(
    client, session, monkeypatch
) -> None:
    """Race guard: a run that flips to cancelled AFTER the worker SELECTs
    it but BEFORE advance_one_step gets to it must not trigger an LLM
    call. This is the defensive `session.refresh(run)` check inside the
    tick body."""
    from chief_editor.llm import registry as reg

    _seed(client)
    # The run must exist for the tick's SELECT to find it; we deliberately
    # ignore the local — the race-cancellation happens inside the patched
    # session.refresh below.
    _ = _make_queued_run(session)
    # Cancel BEFORE the tick — but in a way that simulates a race: the
    # query returns the run (status="queued") and then before the inner
    # loop body refreshes, the status flips. We approximate this by
    # patching session.refresh to set the status on first call.
    original_refresh = session.refresh
    call_count = {"n": 0}

    def _refresh_then_cancel(obj):
        original_refresh(obj)
        if isinstance(obj, GenerationRun) and call_count["n"] == 0:
            call_count["n"] += 1
            obj.status = "cancelled"
            session.add(obj)
            session.commit()
            original_refresh(obj)

    monkeypatch.setattr(session, "refresh", _refresh_then_cancel)

    # Tripwire on LLM
    provider = reg.get_llm_provider()
    llm_calls = {"n": 0}

    def _track(*args, **kwargs):
        llm_calls["n"] += 1
        raise AssertionError("LLM called after race-cancellation")

    monkeypatch.setattr(provider, "complete_json", _track)

    # Force the query to find the run (still queued from pickup).
    _generation_runs_tick(session)
    assert llm_calls["n"] == 0


# ---------------------------------------------------------------------------
# Failure semantics — failed runs are not auto-retried
# ---------------------------------------------------------------------------


def test_failed_run_is_not_retried(client, session, monkeypatch) -> None:
    from chief_editor.llm import registry as reg

    _seed(client)
    run = _make_queued_run(session)

    provider = reg.get_llm_provider()

    def _boom(*args, **kwargs):
        raise RuntimeError("upstream slow")

    monkeypatch.setattr(provider, "complete_json", _boom)

    _generation_runs_tick(session)
    session.refresh(run)
    assert run.status == "failed"

    steps_before = len(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    )

    # Drop the tripwire — even if the LLM started behaving again, the
    # failed run must NOT be picked up.
    monkeypatch.undo()

    advanced = _generation_runs_tick(session)
    assert advanced == 0

    steps_after = len(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    )
    assert steps_after == steps_before


def test_failed_run_does_not_create_post_candidate(client, session, monkeypatch) -> None:
    from chief_editor.llm import registry as reg

    _seed(client)
    cand_before = len(session.exec(select(PostCandidate)).all())
    appr_before = len(session.exec(select(ApprovalDecision)).all())
    job_before = len(session.exec(select(PublishJob)).all())

    run = _make_queued_run(session)
    provider = reg.get_llm_provider()
    monkeypatch.setattr(
        provider, "complete_json", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("x"))
    )

    _generation_runs_tick(session)
    session.refresh(run)
    assert run.status == "failed"
    assert run.candidate_id is None

    assert len(session.exec(select(PostCandidate)).all()) == cand_before
    assert len(session.exec(select(ApprovalDecision)).all()) == appr_before
    assert len(session.exec(select(PublishJob)).all()) == job_before


# ---------------------------------------------------------------------------
# Full workflow over repeated ticks
# ---------------------------------------------------------------------------


def test_full_workflow_completes_over_repeated_ticks(client, session) -> None:
    _seed(client)
    cand_before = len(session.exec(select(PostCandidate)).all())
    appr_before = len(session.exec(select(ApprovalDecision)).all())
    job_before = len(session.exec(select(PublishJob)).all())

    run = _make_queued_run(session)

    # 11 steps total — give the loop 20 ticks max as a safety budget.
    for _ in range(20):
        session.refresh(run)
        if run.status in {"succeeded", "failed", "cancelled"}:
            break
        _generation_runs_tick(session)

    session.refresh(run)
    assert run.status == "succeeded", f"run did not succeed: {run.status} step={run.step_index}"
    assert run.candidate_id is not None

    cands = list(session.exec(select(PostCandidate)).all())
    assert len(cands) == cand_before + 1
    new_cand = next(c for c in cands if c.id == run.candidate_id)
    assert new_cand.status == "draft"

    # Hard rules — worker must not have produced any approval, job, or
    # touched the publishing path.
    assert len(session.exec(select(ApprovalDecision)).all()) == appr_before
    assert len(session.exec(select(PublishJob)).all()) == job_before

    # All 11 step rows + 11 artifacts persisted.
    steps = list(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    )
    artifacts = list(
        session.exec(
            select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
        ).all()
    )
    assert len(steps) == 11
    assert len(artifacts) == 11
    assert all(s.status == "succeeded" for s in steps)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------


def test_tick_writes_generation_runs_heartbeat(client, session) -> None:
    _seed(client)
    _generation_runs_tick(session)
    hb = session.exec(
        select(WorkerHeartbeat).where(
            WorkerHeartbeat.loop_name == "generation_runs"
        )
    ).first()
    assert hb is not None
    assert hb.last_event == "generation_runs.tick"
    assert hb.counter >= 1


def test_heartbeat_written_even_when_no_runs_pending(client, session) -> None:
    """If there are no queued/running runs at all, the loop should still
    heartbeat so the readiness UI does not show the loop as stale."""
    _seed(client)
    advanced = _generation_runs_tick(session)
    assert advanced == 0  # nothing to do
    hb = session.exec(
        select(WorkerHeartbeat).where(
            WorkerHeartbeat.loop_name == "generation_runs"
        )
    ).first()
    assert hb is not None


def test_heartbeat_counter_increments_across_ticks(client, session) -> None:
    _seed(client)
    _generation_runs_tick(session)
    _generation_runs_tick(session)
    hb = session.exec(
        select(WorkerHeartbeat).where(
            WorkerHeartbeat.loop_name == "generation_runs"
        )
    ).first()
    assert hb is not None
    assert hb.counter >= 2


# ---------------------------------------------------------------------------
# Safety regression
# ---------------------------------------------------------------------------


def test_worker_tick_makes_no_live_http_call(client, session, monkeypatch) -> None:
    """Belt-and-braces: the entire generation_runs tick path must not
    instantiate httpx.Client. We patch httpx and assert no call."""
    import httpx

    httpx_calls = {"n": 0}
    original_client = httpx.Client

    def _spy(*args, **kwargs):
        httpx_calls["n"] += 1
        raise AssertionError("httpx.Client instantiated in generation_runs tick")

    monkeypatch.setattr(httpx, "Client", _spy)

    _seed(client)
    run = _make_queued_run(session)
    for _ in range(20):
        session.refresh(run)
        if run.status in {"succeeded", "failed", "cancelled"}:
            break
        _generation_runs_tick(session)

    assert httpx_calls["n"] == 0
    # Restore so teardown / other tests don't break.
    monkeypatch.setattr(httpx, "Client", original_client)
