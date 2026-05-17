"""Time helpers — always UTC-aware, never naive."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hours_since(when: datetime | None) -> float:
    if when is None:
        return 1e9
    delta = utcnow() - to_utc(when)
    return delta.total_seconds() / 3600.0
