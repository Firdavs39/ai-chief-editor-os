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


def telegram_publisher_from_settings(
    target_override: str | None = None,
) -> TelegramPublisher | None:
    """Build a TelegramPublisher.

    The bot token is always resolved the same way (env first, Vault fallback)
    — multi-channel does NOT change how the secret is sourced.

    `target_override` (e.g. a `Channel.target_chat_id`) selects the
    destination chat. When it is empty/None we fall back to the env/Vault
    `target_channel_id` so the default channel keeps working unchanged. A
    publisher is only returned when BOTH a token and a resolved target exist;
    otherwise None (caller falls back to the mock publisher or blocks).
    """
    override = (target_override or "").strip()

    s = get_settings()
    if s.has_telegram_publish:
        target = override or s.telegram_target_channel_id
        if s.telegram_bot_token and target:
            return TelegramPublisher(s.telegram_bot_token, target)
        return None

    # Vault fallback for the token; override wins for the target, else Vault
    # target_channel_id is the default-channel fallback.
    from ..services.integration_config import resolve_provider

    resolved = resolve_provider("telegram_bot")
    token = resolved["bot_token"].value
    target = override or resolved["target_channel_id"].value
    if token and target:
        return TelegramPublisher(token, target)
    return None
