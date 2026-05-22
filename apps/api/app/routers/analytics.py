from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from chief_editor.schemas import AnalyticsResponse
from chief_editor.services.analytics import build_analytics
from chief_editor.services.cost import summary as cost_summary

from ..deps import get_session

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsResponse)
def analytics(session: Session = Depends(get_session)) -> AnalyticsResponse:
    data = build_analytics(session)
    return AnalyticsResponse(**data)


@router.get("/cost")
def cost(
    limit_runs: int = Query(200, ge=1, le=2000),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Phase 10 — per-run and aggregated cost over the most-recent
    `limit_runs` GenerationRuns. USD figures use the in-code price table
    (`chief_editor.services.cost.PRICE_TABLE`); unknown (provider, model)
    pairs contribute 0 cost and are logged at INFO level.

    No raw prompts or completions are exposed — only token counts and
    derived costs.
    """
    return cost_summary(session, limit_runs=limit_runs)
