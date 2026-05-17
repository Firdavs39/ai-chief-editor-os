from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from chief_editor.schemas import AnalyticsResponse
from chief_editor.services.analytics import build_analytics

from ..deps import get_session

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse)
def analytics(session: Session = Depends(get_session)) -> AnalyticsResponse:
    data = build_analytics(session)
    return AnalyticsResponse(**data)
