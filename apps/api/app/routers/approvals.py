from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from chief_editor.models import PostCandidate
from chief_editor.schemas import ApprovalRequest, CandidateOut, PublishJobOut
from chief_editor.services.approval import (
    ApprovalError,
    approve_and_schedule,
    reject_candidate,
)

from ..deps import get_session

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/{candidate_id}/approve")
def approve(
    candidate_id: str,
    payload: ApprovalRequest,
    session: Session = Depends(get_session),
) -> dict:
    cand = session.get(PostCandidate, candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    try:
        decision, job = approve_and_schedule(
            session,
            cand,
            platform=payload.platform,
            reason=payload.reason,
            scheduled_at=payload.scheduled_at,
        )
    except ApprovalError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "candidate": CandidateOut(**cand.model_dump()).model_dump(),
        "job": PublishJobOut(**job.model_dump()).model_dump(),
        "approval_id": decision.id,
    }


@router.post("/{candidate_id}/reject", response_model=CandidateOut)
def reject(
    candidate_id: str,
    payload: ApprovalRequest,
    session: Session = Depends(get_session),
) -> CandidateOut:
    cand = session.get(PostCandidate, candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    reject_candidate(session, cand, reason=payload.reason)
    return CandidateOut(**cand.model_dump())
