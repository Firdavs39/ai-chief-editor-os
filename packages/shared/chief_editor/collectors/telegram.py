"""Read-only Telegram collector via Telethon. Only fetches channels the user can access."""

from __future__ import annotations

import logging
from pathlib import Path

from ..models import Source
from ..settings import Settings, get_settings
from .base import CollectedItem, Collector

log = logging.getLogger(__name__)


def _resolve_telethon_creds(settings: Settings) -> tuple[str, str]:
    """Resolve api_id + api_hash from env first, then the Vault.

    Mirrors the publisher's env→vault fallback so credentials stored via
    the /secrets/telethon endpoint are honoured by the collector.
    """
    if settings.telethon_api_id and settings.telethon_api_hash:
        return settings.telethon_api_id, settings.telethon_api_hash
    try:
        from ..services.integration_config import resolve_provider

        resolved = resolve_provider("telethon")
        return (
            resolved["api_id"].value or "",
            resolved["api_hash"].value or "",
        )
    except Exception as exc:  # noqa: BLE001 — vault optional, never fatal
        log.debug("telethon vault resolution skipped: %s", type(exc).__name__)
        return "", ""


def _session_path(session_name: str) -> str:
    """Full Telethon session path under data/telethon/, matching the
    session-builder script (scripts/create_telethon_session.py)."""
    return str(Path("data/telethon") / (session_name or "chief_editor_session"))


class TelegramCollector(Collector):
    name = "telegram"

    async def fetch(self, source: Source, limit: int = 50) -> list[CollectedItem]:
        settings = get_settings()
        api_id_raw, api_hash = _resolve_telethon_creds(settings)
        if not (api_id_raw and api_hash):
            log.info(
                "telethon credentials missing (env+vault) — skipping telegram collector"
            )
            return []

        try:
            api_id = int(api_id_raw)
        except (TypeError, ValueError):
            log.warning("telethon api_id is not a valid integer — skipping")
            return []

        try:
            from telethon import TelegramClient  # type: ignore
        except ImportError:
            log.warning("telethon not installed — skipping telegram collector")
            return []

        client = TelegramClient(
            _session_path(settings.telethon_session_name),
            api_id,
            api_hash,
        )
        items: list[CollectedItem] = []
        await client.connect()
        try:
            if not await client.is_user_authorized():
                log.warning(
                    "telethon session not authorized — run "
                    "scripts/create_telethon_session.py first — skipping"
                )
                return []
            async for msg in client.iter_messages(source.handle, limit=limit):
                if msg.message is None:
                    continue
                items.append(
                    CollectedItem(
                        external_id=str(msg.id),
                        title="",
                        body=msg.message,
                        url=f"https://t.me/{source.handle.lstrip('@')}/{msg.id}",
                        lang="ru",
                        engagement={
                            "views": getattr(msg, "views", 0) or 0,
                            "forwards": getattr(msg, "forwards", 0) or 0,
                            "replies": getattr(msg.replies, "replies", 0) if msg.replies else 0,
                        },
                        posted_at=msg.date,
                    )
                )
        finally:
            await client.disconnect()
        return items
