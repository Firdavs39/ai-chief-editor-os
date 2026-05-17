from __future__ import annotations

from datetime import datetime

from sqlmodel import Field

from ..time_utils import utcnow
from ._base import TimestampedBase


class ApprovalDecision(TimestampedBase, table=True):
    __tablename__ = "approval_decisions"

    candidate_id: str = Field(foreign_key="post_candidates.id", index=True)
    decision: str = Field(index=True)  # approve | reject | revise
    actor: str = "local-user"
    reason: str = ""
    decided_at: datetime = Field(default_factory=utcnow)
