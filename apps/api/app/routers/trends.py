from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from chief_editor.models import TrendCluster
from chief_editor.schemas import TrendOut

from ..deps import get_session

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("", response_model=list[TrendOut])
def list_trends(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
    min_score: float = Query(0.0, ge=0, le=1),
    category: str | None = None,
) -> list[TrendOut]:
    stmt = select(TrendCluster)
    if category:
        stmt = stmt.where(TrendCluster.category == category)
    stmt = stmt.order_by(TrendCluster.total_score.desc()).limit(limit)
    rows = session.exec(stmt).all()
    return [TrendOut(**r.model_dump()) for r in rows if r.total_score >= min_score]


@router.get("/{cluster_id}", response_model=TrendOut)
def get_trend(cluster_id: str, session: Session = Depends(get_session)) -> TrendOut:
    cluster = session.get(TrendCluster, cluster_id)
    if cluster is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="cluster not found")
    return TrendOut(**cluster.model_dump())
