from __future__ import annotations

from typing import Any

from sqlmodel import Field

from ._base import TimestampedBase, json_column, json_list_column


class StyleProfile(TimestampedBase, table=True):
    __tablename__ = "style_profiles"

    name: str = Field(default="default", unique=True, index=True)
    lang_primary: str = "ru"
    tone: str = ""
    audience: str = ""
    banned_phrases: list[str] = Field(default_factory=list, sa_column=json_list_column())
    example_posts: list[str] = Field(default_factory=list, sa_column=json_list_column())
    writing_rules: str = ""
    target_topics: list[str] = Field(default_factory=list, sa_column=json_list_column())
    voice_sliders: dict[str, Any] = Field(default_factory=dict, sa_column=json_column())
