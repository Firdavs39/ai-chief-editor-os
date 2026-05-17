"""Real Telegram publisher via python-telegram-bot. Sends to a configured channel."""

from __future__ import annotations

import asyncio
import logging

from ..models import PostCandidate, PublishJob
from ..settings import get_settings
from .base import Publisher, PublishOutcome

log = logging.getLogger(__name__)


class TelegramPublisher(Publisher):
    name = "telegram"

    def __init__(self, bot_token: str, target_channel_id: str) -> None:
        self._bot_token = bot_token
        self._target = target_channel_id

    def _dispatch(self, job: PublishJob, candidate: PostCandidate) -> PublishOutcome:
        try:
            from telegram import Bot  # type: ignore
        except ImportError:
            return PublishOutcome(
                success=False,
                error="python-telegram-bot is not installed in this environment",
            )

        body = self.pick_body(candidate, job.platform)
        if len(body) > 4096:
            body = body[:4093] + "..."

        bot = Bot(token=self._bot_token)
        loop = asyncio.new_event_loop()
        try:
            message = loop.run_until_complete(
                bot.send_message(chat_id=self._target, text=body, disable_web_page_preview=False)
            )
        except Exception as exc:  # noqa: BLE001 - we want one summary line
            log.exception("telegram publish failed")
            return PublishOutcome(success=False, error=str(exc))
        finally:
            loop.close()

        url = ""
        if hasattr(message, "link") and message.link:
            url = message.link
        elif hasattr(message, "message_id"):
            url = f"https://t.me/{str(self._target).lstrip('@')}/{message.message_id}"

        return PublishOutcome(success=True, external_url=url)


def telegram_publisher_from_settings() -> TelegramPublisher | None:
    s = get_settings()
    if s.has_telegram_publish:
        return TelegramPublisher(s.telegram_bot_token, s.telegram_target_channel_id)
    # Vault fallback.
    from ..services.integration_config import resolve_provider

    resolved = resolve_provider("telegram_bot")
    token = resolved["bot_token"].value
    target = resolved["target_channel_id"].value
    if token and target:
        return TelegramPublisher(token, target)
    return None
