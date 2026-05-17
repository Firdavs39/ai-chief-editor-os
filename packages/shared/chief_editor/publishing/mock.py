"""Mock publisher: logs to console + returns a synthetic external URL."""

from __future__ import annotations

import logging

from ..models import PostCandidate, PublishJob
from .base import Publisher, PublishOutcome

log = logging.getLogger(__name__)


class MockPublisher(Publisher):
    name = "mock"

    def _dispatch(self, job: PublishJob, candidate: PostCandidate) -> PublishOutcome:
        body = self.pick_body(candidate, job.platform)
        log.info(
            "MOCK PUBLISH platform=%s candidate=%s len=%d preview=%r",
            job.platform,
            candidate.id,
            len(body),
            body[:120],
        )
        return PublishOutcome(
            success=True,
            external_url=f"mock://{job.platform}/{job.id}",
        )
