from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from chief_editor.models import Source
from chief_editor.schemas import SourceIn, SourceOut

from ..deps import get_session

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_session)) -> list[SourceOut]:
    rows = session.exec(select(Source).order_by(Source.created_at.desc())).all()
    return [SourceOut(**r.model_dump()) for r in rows]


@router.post("", response_model=SourceOut, status_code=201)
def create_source(payload: SourceIn, session: Session = Depends(get_session)) -> SourceOut:
    source = Source(**payload.model_dump(), health={"ok": True, "note": "created"})
    session.add(source)
    session.commit()
    session.refresh(source)
    return SourceOut(**source.model_dump())


@router.delete("/{source_id}", status_code=204, response_class=Response)
def delete_source(source_id: str, session: Session = Depends(get_session)) -> Response:
    src = session.get(Source, source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="source not found")
    session.delete(src)
    session.commit()
    return Response(status_code=204)
