from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from chief_editor.models import ApprovalDecision, PostCandidate, PublishJob
from chief_editor.schemas import PublishJobIn, PublishJobOut
from chief_editor.services.approval import approve_and_schedule

from ..deps import get_session

router = APIRouter(prefix="/publishing", tags=["publishing"])


@router.get("/jobs", response_model=list[PublishJobOut])
def list_jobs(
    status: str | None = None,
    session: Session = Depends(get_session),
) -> list[PublishJobOut]:
    stmt = select(PublishJob)
    if status:
        stmt = stmt.where(PublishJob.status == status)
    rows = session.exec(stmt.order_by(PublishJob.scheduled_at.desc())).all()
    return [PublishJobOut(**r.model_dump()) for r in rows]


@router.post("/jobs", response_model=PublishJobOut, status_code=201)
def create_job(
    payload: PublishJobIn,
    session: Session = Depends(get_session),
) -> PublishJobOut:
    cand = session.get(PostCandidate, payload.candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    approval = session.exec(
        select(ApprovalDecision).where(
            (ApprovalDecision.candidate_id == cand.id)
            & (ApprovalDecision.decision == "approve")
        )
    ).first()
    if approval is None:
        raise HTTPException(
            status_code=409,
            detail="cannot create publish job: candidate has no approved decision",
        )
    _, job = approve_and_schedule(
        session,
        cand,
        platform=payload.platform,
        scheduled_at=payload.scheduled_at,
        reason="explicit publish-job creation",
    )
    return PublishJobOut(**job.model_dump())
