"""RSS / Atom collector using feedparser. No credentials required."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from ..models import Source
from .base import CollectedItem, Collector


class RssCollector(Collector):
    name = "rss"

    async def fetch(self, source: Source, limit: int = 50) -> list[CollectedItem]:
        if not source.url:
            return []
        return await asyncio.to_thread(self._fetch_sync, source, limit)

    def _fetch_sync(self, source: Source, limit: int) -> list[CollectedItem]:
        import feedparser

        parsed = feedparser.parse(source.url)
        items: list[CollectedItem] = []
        for entry in parsed.entries[:limit]:
            posted_at: datetime | None = None
            ts = entry.get("published_parsed") or entry.get("updated_parsed")
            if ts is not None:
                posted_at = datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc)
            body = entry.get("summary") or entry.get("description") or ""
            items.append(
                CollectedItem(
                    external_id=entry.get("id") or entry.get("link", "") or entry.get("title", ""),
                    title=entry.get("title", ""),
                    body=body,
                    url=entry.get("link", ""),
                    lang=entry.get("language", "ru"),
                    engagement={},
                    posted_at=posted_at,
                )
            )
        return items
