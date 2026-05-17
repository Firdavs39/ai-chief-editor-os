"""Structured logging — one call to set it up; redacts known secret-shaped keys.

Use:
    from chief_editor.logging_config import configure_logging
    configure_logging(service="api")
"""

from __future__ import annotations

import logging
import os
from typing import Any

import structlog

_SECRET_KEYS = {
    "anthropic_api_key",
    "openai_api_key",
    "telegram_bot_token",
    "telethon_api_hash",
    "reddit_client_secret",
    "postiz_api_key",
    "password",
    "token",
    "secret",
    "api_key",
}


def _redact(_, __, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Drop or mask any structured field that looks like a secret."""
    for key in list(event_dict.keys()):
        kl = key.lower()
        if any(s in kl for s in _SECRET_KEYS):
            value = event_dict[key]
            if isinstance(value, str) and value:
                event_dict[key] = f"<redacted len={len(value)}>"
            else:
                event_dict[key] = "<redacted>"
    return event_dict


def configure_logging(service: str = "service") -> None:
    """Configure stdlib logging + structlog. Idempotent."""
    if getattr(configure_logging, "_done", False):
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    json_mode = os.environ.get("LOG_FORMAT", "").lower() == "json" or os.environ.get(
        "APP_ENV", "dev"
    ) == "prod"

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        timestamper,
        _redact,
    ]

    if json_mode:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Re-route stdlib logging into structlog's processors so existing
    # `logging.getLogger(...)` calls also get redacted + timestamped.
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # bind service name into the contextvars
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=service)

    configure_logging._done = True  # type: ignore[attr-defined]


def get_logger(name: str = "chief_editor") -> Any:
    return structlog.get_logger(name)
