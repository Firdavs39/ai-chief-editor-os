from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Field

from ..time_utils import utcnow
from ._base import TimestampedBase, json_column


class MetricSnapshot(TimestampedBase, table=True):
    __tablename__ = "metric_snapshots"

    subject_type: str = Field(index=True)  # candidate | source | cluster | publish_result
    subject_id: str = Field(index=True)
    metrics: dict[str, Any] = Field(default_factory=dict, sa_column=json_column())
    captured_at: datetime = Field(default_factory=utcnow, index=True)
