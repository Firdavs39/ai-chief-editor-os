from __future__ import annotations

from datetime import datetime

from sqlmodel import Field

from ..time_utils import utcnow
from ._base import TimestampedBase


class WorkerHeartbeat(TimestampedBase, table=True):
    __tablename__ = "worker_heartbeats"

    loop_name: str = Field(unique=True, index=True)
    last_at: datetime = Field(default_factory=utcnow, index=True)
    last_event: str = ""
    counter: int = 0
