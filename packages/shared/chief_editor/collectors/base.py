from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..models import Source


@dataclass
class CollectedItem:
    external_id: str
    title: str = ""
    body: str = ""
    url: str = ""
    lang: str = "ru"
    engagement: dict[str, Any] = field(default_factory=dict)
    posted_at: datetime | None = None


class Collector(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch(self, source: Source, limit: int = 50) -> list[CollectedItem]: ...
