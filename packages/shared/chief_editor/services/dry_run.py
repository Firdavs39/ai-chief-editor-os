"""Dry-run publish — compute the exact payload a publisher would send,
without contacting any external service.

This is used by `/readiness/dry-run-publish/{candidate_id}` and by the worker
when `DRY_RUN_PUBLISH=true`. Returns a flat dict suitable for direct JSON
serialization. **Never** includes secret values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..models import PostCandidate
from ..publishing.base import Publisher
from ..settings import get_settings


def compute_payload(
    candidate: PostCandidate,
    platform: str,
    scheduled_at: datetime | None = None,
) -> dict[str, Any]:
    """Return what the publisher *would* send for a given candidate + platform.

    The output is purely informational. It does not call any publisher.
    """
    settings = get_settings()
    body = Publisher.pick_body(candidate, platform)

    payload: dict[str, Any] = {
        "platform": platform,
        "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
        "candidate_id": candidate.id,
        "candidate_version": candidate.version,
        "candidate_status": candidate.status,
        "body": body,
        "body_length": len(body),
        "cta": candidate.cta,
        "topic": candidate.topic,
    }

    if platform == "telegram":
        payload["limits"] = {"max_length": 4096, "soft_target": 1024}
        payload["target_channel_id_present"] = bool(settings.telegram_target_channel_id)
        payload["bot_token_present"] = bool(settings.telegram_bot_token)
    elif platform == "threads":
        payload["limits"] = {"max_length": 500}
        payload["postiz_base_url_present"] = bool(settings.postiz_base_url)
        payload["postiz_threads_integration_id_present"] = bool(
            settings.postiz_threads_integration_id
        )
    elif platform == "reddit":
        payload["limits"] = {"max_length": 40000}
        payload["postiz_base_url_present"] = bool(settings.postiz_base_url)
        payload["postiz_reddit_integration_id_present"] = bool(
            settings.postiz_reddit_integration_id
        )
    else:
        payload["limits"] = {"max_length": 0}

    payload["safety"] = {
        "publishing_enabled": settings.publishing_enabled,
        "dry_run_publish": settings.dry_run_publish,
        "mock_mode": settings.mock_mode,
    }
    payload["dry_run"] = True
    payload["would_send"] = (
        settings.publishing_enabled and not settings.dry_run_publish and not settings.mock_mode
    )
    return payload
