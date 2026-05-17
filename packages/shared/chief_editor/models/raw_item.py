from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Field

from ._base import TimestampedBase, json_column


class RawItem(TimestampedBase, table=True):
    __tablename__ = "raw_items"

    source_id: str = Field(foreign_key="sources.id", index=True)
    external_id: str = Field(index=True)
    title: str = ""
    body: str = ""
    url: str = ""
    lang: str = "ru"
    engagement: dict[str, Any] = Field(default_factory=dict, sa_column=json_column())
    posted_at: datetime | None = Field(default=None, index=True)
    collected_at: datetime | None = Field(default=None)
    text_hash: str = Field(index=True)
