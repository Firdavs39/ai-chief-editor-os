"""Worker `_dispatch_one()` safety gates: PUBLISHING_ENABLED + DRY_RUN_PUBLISH."""

from __future__ import annotations

from sqlmodel import select

from chief_editor.models import (
    PostCandidate,
    PublishJob,
    PublishResult,
)
from chief_editor.services.approval import approve_and_schedule
from chief_editor.settings import get_settings
from chief_editor.time_utils import utcnow


def _seed_candidate(session) -> PostCandidate:
    cand = PostCandidate(
        topic="x",
        tg_version="hello world",
        threads_version="hello",
        reddit_version="hello world",
        cta="Do it.",
        status="draft",
        viral_score=0.5,
        style_match_score=0.5,
        slop_risk=0.1,
        controversy_risk=0.1,
    )
    session.add(cand)
    session.commit()
    return cand


def test_publishing_blocked_when_master_switch_off(session, monkeypatch) -> None:
    monkeypatch.setenv("PUBLISHING_ENABLED", "false")
    monkeypatch.setenv("DRY_RUN_PUBLISH", "false")
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()

    from worker.main import _dispatch_one

    cand = _seed_candidate(session)
    _, job = approve_and_schedule(session, cand, platform="mock")

    _dispatch_one(session, job)
    session.commit()
    session.refresh(job)

    assert job.status == "blocked"
    result = session.exec(
        select(PublishResult).where(PublishResult.job_id == job.id)
    ).first()
    assert result is not None
    assert result.success is False
    assert "PUBLISHING_ENABLED" in result.error
    assert cand.status == "approved"  # not published


def test_dry_run_produces_dryrun_url_and_does_not_publish(session, monkeypatch) -> None:
    monkeypatch.setenv("PUBLISHING_ENABLED", "true")
    monkeypatch.setenv("DRY_RUN_PUBLISH", "true")
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()

    from worker.main import _dispatch_one

    cand = _seed_candidate(session)
    _, job = approve_and_schedule(session, cand, platform="telegram")

    _dispatch_one(session, job)
    session.commit()
    session.refresh(job)
    session.refresh(cand)

    assert job.status == "dry_run"
    result = session.exec(
        select(PublishResult).where(PublishResult.job_id == job.id)
    ).first()
    assert result is not None
    assert result.success is True
    assert result.external_url.startswith("dryrun://")
    assert cand.status == "approved"  # NOT marked as published in dry-run


def test_dispatch_without_approval_does_not_publish(session, monkeypatch) -> None:
    monkeypatch.setenv("PUBLISHING_ENABLED", "true")
    monkeypatch.setenv("DRY_RUN_PUBLISH", "false")
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()

    from worker.main import _dispatch_one

    cand = _seed_candidate(session)
    # Manually create a job WITHOUT going through approve_and_schedule.
    job = PublishJob(
        candidate_id=cand.id,
        approval_id="",
        platform="mock",
        scheduled_at=utcnow(),
        idempotency_key="no-approval",
        status="pending",
    )
    session.add(job)
    session.commit()

    _dispatch_one(session, job)
    session.commit()
    session.refresh(job)

    assert job.status == "failed"
    result = session.exec(
        select(PublishResult).where(PublishResult.job_id == job.id)
    ).first()
    assert result is not None
    assert result.success is False
    assert "approval" in result.error.lower()


def test_dispatch_publishes_when_all_gates_open(session, monkeypatch) -> None:
    monkeypatch.setenv("PUBLISHING_ENABLED", "true")
    monkeypatch.setenv("DRY_RUN_PUBLISH", "false")
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()

    from worker.main import _dispatch_one

    cand = _seed_candidate(session)
    _, job = approve_and_schedule(session, cand, platform="mock")

    _dispatch_one(session, job)
    session.commit()
    session.refresh(job)
    session.refresh(cand)

    assert job.status == "done"
    result = session.exec(
        select(PublishResult).where(PublishResult.job_id == job.id)
    ).first()
    assert result is not None
    assert result.success is True
    assert result.external_url.startswith("mock://")  # MockPublisher
    assert cand.status == "published"


def test_pending_config_when_live_mode_but_no_publisher(session, monkeypatch) -> None:
    """If LIVE_MODE is on AND MOCK_MODE is off AND no real publisher configured,
    the resolved publisher is MockPublisher — the worker should refuse to use it."""
    monkeypatch.setenv("PUBLISHING_ENABLED", "true")
    monkeypatch.setenv("DRY_RUN_PUBLISH", "false")
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LIVE_MODE", "true")
    get_settings.cache_clear()

    from worker.main import _dispatch_one

    cand = _seed_candidate(session)
    _, job = approve_and_schedule(session, cand, platform="telegram")

    _dispatch_one(session, job)
    session.commit()
    session.refresh(job)

    # No TELEGRAM_BOT_TOKEN configured → registry returns MockPublisher →
    # worker downgrades to pending_config in live mode.
    assert job.status == "pending_config"
