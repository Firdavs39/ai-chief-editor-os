from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from chief_editor.models import Source
from chief_editor.schemas import CollectRunRequest, CollectRunResponse
from chief_editor.services.pipeline import recluster, run_collection_for_source

from ..deps import get_session

router = APIRouter(prefix="/collect", tags=["collect"])


@router.post("/run", response_model=CollectRunResponse)
def collect_run(
    payload: CollectRunRequest | None = None,
    session: Session = Depends(get_session),
) -> CollectRunResponse:
    if payload and payload.source_id:
        src = session.get(Source, payload.source_id)
        sources = [src] if src else []
    else:
        sources = list(session.exec(select(Source).where(Source.enabled == True)).all())  # noqa: E712

    if not sources:
        return CollectRunResponse(
            triggered=False, sources=0, queued=0, note="no enabled sources"
        )

    async def _run_all() -> int:
        inserted_total = 0
        for src in sources:
            inserted_total += await run_collection_for_source(session, src)
        return inserted_total

    inserted = asyncio.run(_run_all())
    new_signals = recluster(session)
    return CollectRunResponse(
        triggered=True,
        sources=len(sources),
        queued=inserted,
        note=f"ingested {inserted} new items; {new_signals} new signals reclustered",
    )
