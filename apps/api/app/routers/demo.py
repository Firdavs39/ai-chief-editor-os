from __future__ import annotations

from fastapi import APIRouter

from chief_editor.services.seed import run_seed

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/seed")
def seed() -> dict:
    summary = run_seed()
    return {"ok": True, "summary": summary}
