"""Heartbeat freshness detection."""

from __future__ import annotations

from datetime import timedelta

from chief_editor.models import WorkerHeartbeat
from chief_editor.time_utils import utcnow


def test_worker_status_unknown_when_no_heartbeats(client) -> None:
    response = client.get("/worker/status")
    body = response.json()
    assert body["overall"] == "unknown"


def test_worker_status_running_when_fresh(session, client) -> None:
    now = utcnow()
    for name in ("collector", "generation", "publisher"):
        session.add(
            WorkerHeartbeat(
                loop_name=name,
                last_at=now,
                last_event=f"{name}.tick",
                counter=1,
            )
        )
    session.commit()

    body = client.get("/worker/status").json()
    assert body["overall"] == "running"
    for name in ("collector", "generation", "publisher"):
        assert body["loops"][name]["fresh"] is True


def test_worker_status_stale_when_age_exceeds_ttl(session, client) -> None:
    stale = utcnow() - timedelta(seconds=600)
    session.add(
        WorkerHeartbeat(
            loop_name="collector", last_at=stale, last_event="collector.tick", counter=1
        )
    )
    session.commit()

    body = client.get("/worker/status").json()
    assert body["overall"] in {"stale", "partial"}
    assert body["loops"]["collector"]["fresh"] is False
