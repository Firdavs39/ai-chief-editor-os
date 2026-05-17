from __future__ import annotations

from typing import Any

from sqlmodel import Field

from ._base import TimestampedBase, json_column


class SystemLog(TimestampedBase, table=True):
    __tablename__ = "system_logs"

    level: str = Field(default="info", index=True)
    event: str = Field(index=True)
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict, sa_column=json_column())
