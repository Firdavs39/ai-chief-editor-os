from __future__ import annotations

from sqlmodel import Field

from ._base import TimestampedBase, json_list_column


class PostCandidate(TimestampedBase, table=True):
    __tablename__ = "post_candidates"

    cluster_id: str | None = Field(default=None, foreign_key="trend_clusters.id", index=True)
    # Outbound channel this candidate belongs to. Set by the finalizer from
    # the run's channel_id. NULL on legacy candidates → default channel target
    # is used at dispatch (never a silent wrong-chat default).
    channel_id: str | None = Field(default=None, foreign_key="channels.id", index=True)
    topic: str = ""
    source_summary: str = ""
    why_it_matters: str = ""
    psychology_hook: str = ""
    tg_version: str = ""
    threads_version: str = ""
    reddit_version: str = ""
    cta: str = ""

    style_match_score: float = 0.0
    viral_score: float = 0.0
    slop_risk: float = 0.0
    controversy_risk: float = 0.0

    recommendation: str = ""
    critic_notes: list[dict] = Field(default_factory=list, sa_column=json_list_column())

    status: str = Field(default="draft", index=True)
    version: int = 1
