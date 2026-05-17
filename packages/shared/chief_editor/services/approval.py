"""Approval + publish-job creation. The single API-level gate."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlmodel import Session

from ..models import ApprovalDecision, PostCandidate, PublishJob
from ..time_utils import utcnow


class ApprovalError(RuntimeError):
    pass


def _idempotency_key(candidate_id: str, scheduled_at: datetime, platform: str) -> str:
    raw = f"{candidate_id}|{platform}|{int(scheduled_at.timestamp())}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def approve_and_schedule(
    session: Session,
    candidate: PostCandidate,
    *,
    platform: str = "telegram",
    reason: str = "",
    actor: str = "local-user",
    scheduled_at: datetime | None = None,
) -> tuple[ApprovalDecision, PublishJob]:
    if candidate.status == "rejected":
        raise ApprovalError("cannot approve a rejected candidate")

    decision = ApprovalDecision(
        candidate_id=candidate.id,
        decision="approve",
        actor=actor,
        reason=reason,
        decided_at=utcnow(),
    )
    candidate.status = "approved"
    session.add(candidate)
    session.add(decision)
    session.flush()

    when = scheduled_at or (utcnow() + timedelta(minutes=5))
    job = PublishJob(
        candidate_id=candidate.id,
        approval_id=decision.id,
        platform=platform,
        scheduled_at=when,
        status="pending",
        idempotency_key=_idempotency_key(candidate.id, when, platform),
    )
    session.add(job)
    session.commit()
    # Pydantic v2 `model_dump()` reads `__dict__` directly. SQLAlchemy expires
    # all attributes on commit, leaving `__dict__` empty — `cand.model_dump()`
    # in the API route would then serialize as `{}`. Refresh all three to
    # repopulate before returning.
    session.refresh(candidate)
    session.refresh(decision)
    session.refresh(job)
    return decision, job


def reject_candidate(
    session: Session,
    candidate: PostCandidate,
    *,
    reason: str = "",
    actor: str = "local-user",
) -> ApprovalDecision:
    decision = ApprovalDecision(
        candidate_id=candidate.id,
        decision="reject",
        actor=actor,
        reason=reason,
        decided_at=utcnow(),
    )
    candidate.status = "rejected"
    session.add(candidate)
    session.add(decision)
    session.commit()
    # See note in approve_and_schedule — refresh so model_dump() returns full data.
    session.refresh(candidate)
    session.refresh(decision)
    return decision
