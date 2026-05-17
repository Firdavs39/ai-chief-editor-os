"""Read-only Telegram collector via Telethon. Only fetches channels the user can access."""

from __future__ import annotations

import logging

from ..models import Source
from ..settings import get_settings
from .base import CollectedItem, Collector

log = logging.getLogger(__name__)


class TelegramCollector(Collector):
    name = "telegram"

    async def fetch(self, source: Source, limit: int = 50) -> list[CollectedItem]:
        settings = get_settings()
        if not settings.has_telethon:
            log.info("telethon credentials missing — skipping telegram collector")
            return []

        try:
            from telethon import TelegramClient  # type: ignore
        except ImportError:
            log.warning("telethon not installed — skipping telegram collector")
            return []

        client = TelegramClient(
            settings.telethon_session_name,
            int(settings.telethon_api_id),
            settings.telethon_api_hash,
        )
        items: list[CollectedItem] = []
        await client.connect()
        try:
            if not await client.is_user_authorized():
                log.warning("telethon session not authorized — skipping")
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
