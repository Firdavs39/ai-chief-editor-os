"""Source collectors — Telegram, Reddit, RSS, mock."""

from .base import CollectedItem, Collector
from .registry import get_collector_for

__all__ = ["Collector", "CollectedItem", "get_collector_for"]
