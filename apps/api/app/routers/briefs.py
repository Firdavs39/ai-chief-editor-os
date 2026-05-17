from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from chief_editor.models import TrendCluster
from chief_editor.schemas import CandidateOut
from chief_editor.services.candidate import generate_for_cluster

from ..deps import get_session

router = APIRouter(prefix="/brief", tags=["briefs"])


class BriefGenerateRequest(BaseModel):
    cluster_id: str | None = None
    top_n: int = 3


@router.post("/generate", response_model=list[CandidateOut])
def generate(
    payload: BriefGenerateRequest,
    session: Session = Depends(get_session),
) -> list[CandidateOut]:
    if payload.cluster_id:
        cluster = session.get(TrendCluster, payload.cluster_id)
        clusters = [cluster] if cluster else []
    else:
        clusters = list(
            session.exec(
                select(TrendCluster).order_by(TrendCluster.total_score.desc()).limit(payload.top_n)
            ).all()
        )

    out: list[CandidateOut] = []
    for cluster in clusters:
        candidate = generate_for_cluster(session, cluster)
        out.append(CandidateOut(**candidate.model_dump()))
    return out
