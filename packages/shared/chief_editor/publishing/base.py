"""Publisher base class. The single ground-truth gate on outbound posts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import ApprovalDecision, PostCandidate, PublishJob


class ApprovalRequiredError(RuntimeError):
    """Raised if a publisher is asked to send without an approved decision."""


@dataclass
class PublishOutcome:
    success: bool
    external_url: str = ""
    error: str = ""


class Publisher(ABC):
    name: str = "base"

    def publish(
        self,
        job: PublishJob,
        candidate: PostCandidate,
        approval: ApprovalDecision | None,
    ) -> PublishOutcome:
        """Hard gate. Subclasses must call into this via _dispatch only."""
        if approval is None or approval.decision != "approve":
            raise ApprovalRequiredError(
                f"refusing to publish candidate={candidate.id}: no approve decision"
            )
        if candidate.status == "rejected":
            raise ApprovalRequiredError(
                f"refusing to publish candidate={candidate.id}: candidate rejected"
            )
        return self._dispatch(job, candidate)

    @abstractmethod
    def _dispatch(self, job: PublishJob, candidate: PostCandidate) -> PublishOutcome: ...

    @staticmethod
    def pick_body(candidate: PostCandidate, platform: str) -> str:
        if platform == "telegram":
            return candidate.tg_version
        if platform == "threads":
            return candidate.threads_version
        if platform == "reddit":
            return candidate.reddit_version
        return candidate.tg_version
