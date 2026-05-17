from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Field

from ._base import TimestampedBase, json_column


class Source(TimestampedBase, table=True):
    __tablename__ = "sources"

    kind: str = Field(index=True)
    handle: str = Field(index=True)
    url: str = ""
    title: str = ""
    weight: float = Field(default=5.0)
    enabled: bool = Field(default=True)
    last_collected_at: datetime | None = Field(default=None)
    health: dict[str, Any] = Field(default_factory=dict, sa_column=json_column())
