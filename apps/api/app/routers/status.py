from __future__ import annotations

from fastapi import APIRouter

from chief_editor.llm import get_llm_provider
from chief_editor.schemas import StatusResponse
from chief_editor.settings import get_settings

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    settings = get_settings()
    provider = get_llm_provider()
    return StatusResponse(
        ok=True,
        app_env=settings.app_env,
        mock_mode=settings.mock_mode,
        demo_mode=settings.demo_mode,
        live_mode=settings.live_mode,
        dry_run_publish=settings.dry_run_publish,
        publishing_enabled=settings.publishing_enabled,
        llm_provider=provider.name,
        timezone=settings.timezone,
        adapters={
            "anthropic": settings.has_anthropic,
            "openai": settings.has_openai,
            "telethon": settings.has_telethon,
            "reddit": settings.has_reddit,
            "telegram_publish": settings.has_telegram_publish,
            "postiz": settings.has_postiz,
        },
    )
