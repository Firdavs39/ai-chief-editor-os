"""Shared base mixin: UUID PK + timestamps + JSON column helper."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from ..time_utils import utcnow


def new_uuid() -> str:
    return str(uuid.uuid4())


def json_column() -> Any:
    return Column(JSON, nullable=False, default=dict)


def json_list_column() -> Any:
    return Column(JSON, nullable=False, default=list)


class TimestampedBase(SQLModel):
    id: str = Field(default_factory=new_uuid, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
