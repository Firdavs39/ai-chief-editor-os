"""Worker status — derived from WorkerHeartbeat + recent SystemLog events."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from chief_editor.models import SystemLog, WorkerHeartbeat
from chief_editor.settings import get_settings
from chief_editor.time_utils import to_utc, utcnow

from ..deps import get_session

router = APIRouter(prefix="/worker", tags=["worker"])


def _last_event(session: Session, event: str) -> SystemLog | None:
    return session.exec(
        select(SystemLog).where(SystemLog.event == event).order_by(SystemLog.created_at.desc())
    ).first()


@router.get("/status")
def worker_status(session: Session = Depends(get_session)) -> dict[str, Any]:
    s = get_settings()
    ttl = max(15, s.worker_heartbeat_ttl_seconds)
    now = utcnow()

    heartbeats = list(session.exec(select(WorkerHeartbeat)).all())
    loops: dict[str, dict[str, Any]] = {}
    fresh_count = 0
    for hb in heartbeats:
        last_at = to_utc(hb.last_at) if hb.last_at else None
        age = (now - last_at).total_seconds() if last_at else 1e9
        fresh = age <= ttl
        if fresh:
            fresh_count += 1
        loops[hb.loop_name] = {
            "last_at": last_at.isoformat() if last_at else None,
            "last_event": hb.last_event,
            "age_seconds": int(age),
            "fresh": fresh,
            "counter": hb.counter,
        }

    if not heartbeats:
        overall = "unknown"
    elif fresh_count == len(heartbeats):
        overall = "running"
    elif fresh_count > 0:
        overall = "partial"
    else:
        overall = "stale"

    last_collect = _last_event(session, "collector.tick")
    last_generate = _last_event(session, "generator.tick")
    last_publish = _last_event(session, "publisher.dispatch")

    return {
        "ok": True,
        "overall": overall,
        "ttl_seconds": ttl,
        "loops": loops,
        "last_events": {
            "collector_tick": last_collect.created_at.isoformat() if last_collect else None,
            "generator_tick": last_generate.created_at.isoformat() if last_generate else None,
            "publisher_dispatch": last_publish.created_at.isoformat() if last_publish else None,
        },
        "intervals": {
            "collect": s.collect_interval_seconds,
            "generate": s.generate_interval_seconds,
            "publish": s.publish_interval_seconds,
        },
        "checked_at": now.isoformat(),
    }
