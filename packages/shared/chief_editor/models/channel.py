"""Channel / ChannelSource — multi-channel publishing model.

A `Channel` is one outbound destination (e.g. a single Telegram channel)
with its own style profile and its own subset of parsing sources. This is
what lets one deployment run several Telegram channels, each with a distinct
voice and a distinct source pool.

Security note — a Channel NEVER stores a secret:
- `target_chat_id` is a public identifier (e.g. ``@buai_uz`` or ``-100123``).
- The bot token stays in the Integration Secrets Vault, keyed by
  `bot_provider` (default ``telegram_bot``). This model only records WHICH
  provider to resolve the token from, never the token itself.

`ChannelSource` is the many-to-many link between channels and sources: one
`Source` can feed several channels, and a channel draws only from the
sources linked to it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from ._base import TimestampedBase, json_column


class Channel(TimestampedBase, table=True):
    __tablename__ = "channels"

    name: str = Field(default="", max_length=120)
    slug: str = Field(default="", unique=True, index=True, max_length=80)

    platform: str = Field(default="telegram", index=True, max_length=24)
    # telegram | threads | reddit — the outbound platform for this channel.

    # Public destination identifier (channel username or numeric chat id).
    # NEVER a secret. The bot token lives in the Vault under `bot_provider`.
    target_chat_id: str = Field(default="", max_length=128)

    bot_provider: str = Field(default="telegram_bot", max_length=48)
    # Vault provider key used to resolve the publish credentials.

    lang: str = Field(default="ru", max_length=8)

    style_profile_id: str | None = Field(
        default=None, foreign_key="style_profiles.id", index=True
    )

    enabled: bool = Field(default=True, index=True)
    is_default: bool = Field(default=False, index=True)

    settings: dict[str, Any] = Field(default_factory=dict, sa_column=json_column())


class ChannelSource(TimestampedBase, table=True):
    __tablename__ = "channel_sources"
    __table_args__ = (
        UniqueConstraint(
            "channel_id", "source_id", name="uq_channel_source"
        ),
    )

    channel_id: str = Field(foreign_key="channels.id", index=True)
    source_id: str = Field(foreign_key="sources.id", index=True)
