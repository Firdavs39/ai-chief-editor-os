"""Pick a publisher by platform with mock fallback."""

from __future__ import annotations

import logging

from ..settings import get_settings
from .base import Publisher
from .mock import MockPublisher

log = logging.getLogger(__name__)


def get_publisher(platform: str, target_chat_id: str | None = None) -> Publisher:
    """Resolve a publisher for `platform`.

    `target_chat_id` (a public `Channel.target_chat_id`) overrides the default
    destination for the telegram platform so different channels publish to
    different chats with the same bot token. It is never a secret. Passing
    None preserves the prior single-channel behaviour (env/Vault target).
    """
    settings = get_settings()
    if settings.mock_mode:
        return MockPublisher()

    if platform == "telegram":
        from .telegram import telegram_publisher_from_settings

        pub = telegram_publisher_from_settings(target_override=target_chat_id)
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
