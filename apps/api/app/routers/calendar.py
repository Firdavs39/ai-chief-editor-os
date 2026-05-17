from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from chief_editor.models import PostCandidate, PublishJob
from chief_editor.schemas import CalendarEntry

from ..deps import get_session

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("", response_model=list[CalendarEntry])
def list_calendar(
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[CalendarEntry]:
    if since is None:
        since = datetime.now(tz=timezone.utc) - timedelta(days=14)
    if until is None:
        until = datetime.now(tz=timezone.utc) + timedelta(days=14)

    jobs = session.exec(
        select(PublishJob)
        .where(PublishJob.scheduled_at >= since)
        .where(PublishJob.scheduled_at <= until)
        .order_by(PublishJob.scheduled_at.asc())
    ).all()

    out: list[CalendarEntry] = []
    for job in jobs:
        cand = session.get(PostCandidate, job.candidate_id)
        if cand is None:
            continue
        out.append(
            CalendarEntry(
                job_id=job.id,
                candidate_id=cand.id,
                topic=cand.topic,
                platform=job.platform,
                scheduled_at=job.scheduled_at,
                status=job.status,
                cta=cand.cta,
                tg_preview=(cand.tg_version or "")[:160],
                threads_preview=(cand.threads_version or "")[:160],
            )
        )
    return out
