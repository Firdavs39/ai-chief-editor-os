"""Postiz publisher — official integrations only (Threads, Reddit, others)."""

from __future__ import annotations

import logging

import httpx

from ..models import PostCandidate, PublishJob
from ..settings import get_settings
from .base import Publisher, PublishOutcome

log = logging.getLogger(__name__)


class PostizPublisher(Publisher):
    name = "postiz"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        threads_integration_id: str = "",
        reddit_integration_id: str = "",
    ) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._integrations = {
            "threads": threads_integration_id,
            "reddit": reddit_integration_id,
        }

    def _dispatch(self, job: PublishJob, candidate: PostCandidate) -> PublishOutcome:
        body = self.pick_body(candidate, job.platform)
        integration_id = self._integrations.get(job.platform, "")
        if not integration_id:
            return PublishOutcome(
                success=False,
                error=f"no Postiz integration configured for platform={job.platform}",
            )

        payload = {
            "integrationId": integration_id,
            "scheduleAt": job.scheduled_at.isoformat(),
            "post": [{"value": body}],
        }
        headers = {"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"}
        url = f"{self._base}/api/posts"

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                return PublishOutcome(
                    success=False, error=f"postiz {resp.status_code}: {resp.text[:300]}"
                )
            data = resp.json() if resp.content else {}
            external_url = data.get("url") or data.get("postUrl") or ""
            return PublishOutcome(success=True, external_url=external_url)
        except httpx.HTTPError as exc:
            log.exception("postiz publish failed")
            return PublishOutcome(success=False, error=str(exc))


def postiz_publisher_from_settings() -> PostizPublisher | None:
    s = get_settings()
    if s.has_postiz:
        return PostizPublisher(
            s.postiz_base_url,
            s.postiz_api_key,
            s.postiz_threads_integration_id,
            s.postiz_reddit_integration_id,
        )
    # Vault fallback.
    from ..services.integration_config import resolve_provider

    resolved = resolve_provider("postiz")
    base_url = resolved["base_url"].value
    api_key = resolved["api_key"].value
    if base_url and api_key:
        return PostizPublisher(
            base_url,
            api_key,
            resolved["threads_integration_id"].value or "",
            resolved["reddit_integration_id"].value or "",
        )
    return None
