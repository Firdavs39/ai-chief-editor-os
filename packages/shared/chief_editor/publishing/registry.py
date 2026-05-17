"""Pick a publisher by platform with mock fallback."""

from __future__ import annotations

import logging

from ..settings import get_settings
from .base import Publisher
from .mock import MockPublisher

log = logging.getLogger(__name__)


def get_publisher(platform: str) -> Publisher:
    settings = get_settings()
    if settings.mock_mode:
        return MockPublisher()

    if platform == "telegram":
        from .telegram import telegram_publisher_from_settings

        pub = telegram_publisher_from_settings()
        if pub is None:
            log.warning("telegram credentials missing — using mock publisher")
            return MockPublisher()
        return pub

    if platform in {"threads", "reddit"}:
        from .postiz import postiz_publisher_from_settings

        pub = postiz_publisher_from_settings()
        if pub is None:
            log.warning("postiz credentials missing for %s — using mock publisher", platform)
            return MockPublisher()
        return pub

    return MockPublisher()
