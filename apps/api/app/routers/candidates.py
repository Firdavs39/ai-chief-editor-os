from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from chief_editor.models import PostCandidate
from chief_editor.schemas import CandidateOut, RewriteRequest
from chief_editor.services.candidate import rewrite_candidate

from ..deps import get_session

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("", response_model=list[CandidateOut])
def list_candidates(
    status: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> list[CandidateOut]:
    stmt = select(PostCandidate)
    if status:
        stmt = stmt.where(PostCandidate.status == status)
    stmt = stmt.order_by(PostCandidate.created_at.desc()).limit(limit)
    rows = session.exec(stmt).all()
    return [CandidateOut(**r.model_dump()) for r in rows]


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: str, session: Session = Depends(get_session)) -> CandidateOut:
    cand = session.get(PostCandidate, candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    return CandidateOut(**cand.model_dump())


@router.post("/{candidate_id}/rewrite", response_model=CandidateOut)
def rewrite(
    candidate_id: str,
    payload: RewriteRequest,
    session: Session = Depends(get_session),
) -> CandidateOut:
    cand = session.get(PostCandidate, candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    updated = rewrite_candidate(session, cand, payload.mode, payload.target)
    return CandidateOut(**updated.model_dump())
