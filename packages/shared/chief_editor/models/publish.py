from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Field

from ._base import TimestampedBase, json_column


class PublishJob(TimestampedBase, table=True):
    __tablename__ = "publish_jobs"

    candidate_id: str = Field(foreign_key="post_candidates.id", index=True)
    approval_id: str = Field(foreign_key="approval_decisions.id")
    platform: str = Field(index=True)  # telegram | threads | reddit | mock
    scheduled_at: datetime = Field(index=True)
    status: str = Field(default="pending", index=True)  # pending | running | done | failed
    idempotency_key: str = Field(index=True)


class PublishResult(TimestampedBase, table=True):
    __tablename__ = "publish_results"

    job_id: str = Field(foreign_key="publish_jobs.id", index=True)
    external_url: str = ""
    success: bool = False
    error: str = ""
    metrics_snapshot_at_publish: dict[str, Any] = Field(
        default_factory=dict, sa_column=json_column()
    )
