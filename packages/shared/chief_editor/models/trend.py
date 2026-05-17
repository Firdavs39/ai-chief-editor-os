from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import Field

from ._base import TimestampedBase, json_column, json_list_column


class TrendCluster(TimestampedBase, table=True):
    __tablename__ = "trend_clusters"

    representative_text: str = ""
    keywords: list[str] = Field(default_factory=list, sa_column=json_list_column())
    category: str = ""
    signal_count: int = 0
    first_seen_at: datetime | None = Field(default=None)
    last_seen_at: datetime | None = Field(default=None, index=True)
    score_breakdown: dict[str, float] = Field(default_factory=dict, sa_column=json_column())
    total_score: float = Field(default=0.0, index=True)
    sources_summary: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=json_list_column()
    )


class TrendSignal(TimestampedBase, table=True):
    __tablename__ = "trend_signals"

    cluster_id: str = Field(foreign_key="trend_clusters.id", index=True)
    raw_item_id: str = Field(foreign_key="raw_items.id", index=True)
    similarity: float = 1.0
