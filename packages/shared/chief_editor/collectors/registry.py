"""Pick a collector for a given source.

Telegram (Telethon) and Reddit collectors prefer env credentials; if those
are not set they consult the encrypted vault. RSS needs nothing. Mock mode
overrides everything.
"""

from __future__ import annotations

from ..models import Source
from ..services.integration_config import resolve_provider
from ..settings import get_settings
from .base import Collector
from .mock import MockCollector


def _telethon_ready() -> bool:
    s = get_settings()
    if s.has_telethon:
        return True
    resolved = resolve_provider("telethon")
    return bool(resolved["api_id"].value and resolved["api_hash"].value)


def _reddit_ready() -> bool:
    s = get_settings()
    if s.has_reddit:
        return True
    resolved = resolve_provider("reddit")
    return bool(resolved["client_id"].value and resolved["client_secret"].value)


def get_collector_for(source: Source) -> Collector:
    settings = get_settings()
    if settings.mock_mode:
        return MockCollector()

    if source.kind == "telegram":
        if not _telethon_ready():
            return MockCollector()
        from .telegram import TelegramCollector

        return TelegramCollector()

    if source.kind == "reddit":
        if not _reddit_ready():
            return MockCollector()
        from .reddit import RedditCollector

        return RedditCollector()

    if source.kind == "rss":
        from .rss import RssCollector

        return RssCollector()

    return MockCollector()
