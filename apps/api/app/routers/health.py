from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "ai-chief-editor-os-api"}
