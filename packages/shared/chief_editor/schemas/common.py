from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StatusResponse(BaseModel):
    ok: bool = True
    app_env: str
    mock_mode: bool
    demo_mode: bool = True
    live_mode: bool = False
    dry_run_publish: bool = True
    publishing_enabled: bool = False
    llm_provider: str
    timezone: str
    adapters: dict[str, bool]


class SourceIn(BaseModel):
    kind: Literal["telegram", "reddit", "rss", "manual"]
    handle: str
    url: str = ""
    title: str = ""
    weight: float = 5.0
    enabled: bool = True


class SourceOut(BaseModel):
    id: str
    kind: str
    handle: str
    url: str
    title: str
    weight: float
    enabled: bool
    last_collected_at: datetime | None
    health: dict[str, Any]
    created_at: datetime


class TrendOut(BaseModel):
    id: str
    representative_text: str
    keywords: list[str]
    category: str
    signal_count: int
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    score_breakdown: dict[str, float]
    total_score: float
    sources_summary: list[dict[str, Any]]


class CollectRunRequest(BaseModel):
    source_id: str | None = None


class CollectRunResponse(BaseModel):
    triggered: bool
    sources: int
    queued: int
    note: str = ""


class CandidateOut(BaseModel):
    id: str
    cluster_id: str | None
    topic: str
    source_summary: str
    why_it_matters: str
    psychology_hook: str
    tg_version: str
    threads_version: str
    reddit_version: str
    cta: str
    style_match_score: float
    viral_score: float
    slop_risk: float
    controversy_risk: float
    recommendation: str
    critic_notes: list[dict[str, Any]]
    status: str
    version: int
    created_at: datetime


class RewriteRequest(BaseModel):
    mode: Literal["sharper", "expert", "shorter", "human", "deslop"]
    target: Literal["tg", "threads", "reddit"] = "tg"


class ApprovalRequest(BaseModel):
    reason: str = ""
    scheduled_at: datetime | None = None
    platform: Literal["telegram", "threads", "reddit", "mock"] = "telegram"


class PublishJobIn(BaseModel):
    candidate_id: str
    platform: Literal["telegram", "threads", "reddit", "mock"] = "telegram"
    scheduled_at: datetime | None = None


class PublishJobOut(BaseModel):
    id: str
    candidate_id: str
    approval_id: str
    platform: str
    scheduled_at: datetime
    status: str
    idempotency_key: str
    created_at: datetime


class CalendarEntry(BaseModel):
    job_id: str
    candidate_id: str
    topic: str
    platform: str
    scheduled_at: datetime
    status: str
    cta: str
    tg_preview: str
    threads_preview: str


class StyleProfileIn(BaseModel):
    tone: str
    audience: str
    banned_phrases: list[str] = Field(default_factory=list)
    example_posts: list[str] = Field(default_factory=list)
    writing_rules: str = ""
    target_topics: list[str] = Field(default_factory=list)
    voice_sliders: dict[str, Any] = Field(default_factory=dict)
    lang_primary: str = "ru"


class StyleProfileOut(StyleProfileIn):
    id: str
    name: str
    updated_at: datetime


class AnalyticsResponse(BaseModel):
    by_hook_type: list[dict[str, Any]]
    by_source: list[dict[str, Any]]
    best_patterns: list[dict[str, Any]]
    learning_timeline: list[dict[str, Any]]
    totals: dict[str, Any]
