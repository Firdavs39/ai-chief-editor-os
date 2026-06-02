"""Channel service — default-channel migration, backfill, and link helpers.

The multi-channel model is additive on top of a single-channel deployment.
`ensure_default_channel` performs the one-time (idempotent) migration that
makes existing data multi-channel-aware:

1. Create the default `Channel` (``slug="buai-uz"``, ``is_default=True``) if
   it does not already exist. Its `target_chat_id` is taken from
   ``settings.telegram_target_channel_id`` (public id only — never a token),
   and its `style_profile_id` points at the existing ``name="default"``
   StyleProfile when present.
2. Link every existing `Source` to the default channel via `ChannelSource`.
3. Backfill `GenerationRun.channel_id` and `PostCandidate.channel_id` to the
   default channel wherever they are NULL.

Every step is idempotent: re-running creates no duplicates and overwrites no
operator edits (the default channel's target is only re-stamped when it is
still empty).

This module never reads, writes, or logs a secret. `target_chat_id` is a
public channel identifier; the bot token stays in the Vault, resolved later
by the publisher via `Channel.bot_provider`.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from ..models import (
    Channel,
    ChannelSource,
    GenerationRun,
    PostCandidate,
    Source,
    StyleProfile,
)
from ..settings import get_settings
from ..time_utils import utcnow

log = logging.getLogger("chief_editor.channels")

DEFAULT_CHANNEL_NAME = "buai_uz"
DEFAULT_CHANNEL_SLUG = "buai-uz"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase, hyphenated slug. Falls back to 'channel' when empty."""
    base = _SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    return base or "channel"


def get_default_channel(session: Session) -> Channel | None:
    """Return the default channel, or None if the migration hasn't run."""
    return session.exec(
        select(Channel).where(Channel.is_default == True)  # noqa: E712
    ).first()


def _default_style_profile_id(session: Session) -> str | None:
    profile = session.exec(
        select(StyleProfile).where(StyleProfile.name == "default")
    ).first()
    return profile.id if profile else None


def ensure_channel_columns(engine: Engine) -> list[str]:
    """Add multi-channel columns that `SQLModel.metadata.create_all` cannot.

    create_all only CREATES missing tables; it never ALTERs an existing one.
    A deployment that predates the multi-channel work already has
    `generation_runs` / `post_candidates` tables WITHOUT `channel_id`, so the
    ORM (which now selects that column) fails with "no such column". This adds
    the column in-place. SQLite-only, idempotent, non-destructive (the new
    column is nullable). Other dialects must use a real migration tool.

    Returns the list of `table.column` entries actually added.
    """
    if engine.dialect.name != "sqlite":
        return []  # Postgres/etc. -> use Alembic or equivalent, not this shim.

    targets = {
        "generation_runs": "channel_id",
        "post_candidates": "channel_id",
    }
    added: list[str] = []
    with engine.begin() as conn:
        for table, col in targets.items():
            rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
            if not rows:
                # Table doesn't exist yet -> create_all will make it fresh with
                # the column. Nothing to ALTER.
                continue
            existing = {r[1] for r in rows}
            if col not in existing:
                conn.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR"
                )
                added.append(f"{table}.{col}")
    if added:
        log.info("channels.columns.added %s", ", ".join(added))
    return added


def ensure_default_channel(session: Session) -> Channel:
    """Idempotently create the default channel, link sources, backfill FKs.

    Returns the default Channel. Safe to call repeatedly (e.g. on every
    `init_db`): existing rows are reused, links are de-duplicated, and the
    backfill only touches NULL FKs.
    """
    settings = get_settings()

    channel = get_default_channel(session)
    if channel is None:
        channel = Channel(
            name=DEFAULT_CHANNEL_NAME,
            slug=DEFAULT_CHANNEL_SLUG,
            platform="telegram",
            target_chat_id=(settings.telegram_target_channel_id or ""),
            bot_provider="telegram_bot",
            lang="ru",
            style_profile_id=_default_style_profile_id(session),
            enabled=True,
            is_default=True,
            settings={},
        )
        session.add(channel)
        session.commit()
        session.refresh(channel)
        log.info("channels.default.created slug=%s", channel.slug)
    else:
        # Re-attach a style profile if one now exists and the channel has none
        # (e.g. channel created before the default profile was seeded).
        if channel.style_profile_id is None:
            sp_id = _default_style_profile_id(session)
            if sp_id is not None:
                channel.style_profile_id = sp_id
                channel.updated_at = utcnow()
                session.add(channel)
                session.commit()
                session.refresh(channel)

    _link_all_sources(session, channel)
    _backfill_channel_fks(session, channel)
    return channel


def _link_all_sources(session: Session, channel: Channel) -> int:
    """Link every Source to `channel` if not already linked. Idempotent."""
    linked_ids = {
        cs.source_id
        for cs in session.exec(
            select(ChannelSource).where(ChannelSource.channel_id == channel.id)
        ).all()
    }
    sources = list(session.exec(select(Source)).all())
    added = 0
    for src in sources:
        if src.id in linked_ids:
            continue
        session.add(ChannelSource(channel_id=channel.id, source_id=src.id))
        added += 1
    if added:
        session.commit()
        log.info("channels.default.sources_linked count=%d", added)
    return added


def _backfill_channel_fks(session: Session, channel: Channel) -> tuple[int, int]:
    """Set channel_id on legacy runs/candidates where NULL. Idempotent."""
    runs = list(
        session.exec(
            select(GenerationRun).where(GenerationRun.channel_id == None)  # noqa: E711
        ).all()
    )
    for run in runs:
        run.channel_id = channel.id
        run.updated_at = utcnow()
        session.add(run)

    cands = list(
        session.exec(
            select(PostCandidate).where(PostCandidate.channel_id == None)  # noqa: E711
        ).all()
    )
    for cand in cands:
        cand.channel_id = channel.id
        cand.updated_at = utcnow()
        session.add(cand)

    if runs or cands:
        session.commit()
        log.info(
            "channels.default.backfill runs=%d candidates=%d",
            len(runs),
            len(cands),
        )
    return len(runs), len(cands)


def link_source(session: Session, channel_id: str, source_id: str) -> ChannelSource:
    """Link a source to a channel. Returns the existing link if present."""
    existing = session.exec(
        select(ChannelSource).where(
            (ChannelSource.channel_id == channel_id)
            & (ChannelSource.source_id == source_id)
        )
    ).first()
    if existing is not None:
        return existing
    link = ChannelSource(channel_id=channel_id, source_id=source_id)
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


def unlink_source(session: Session, channel_id: str, source_id: str) -> bool:
    """Remove a channel↔source link. Returns True if a row was deleted."""
    existing = session.exec(
        select(ChannelSource).where(
            (ChannelSource.channel_id == channel_id)
            & (ChannelSource.source_id == source_id)
        )
    ).first()
    if existing is None:
        return False
    session.delete(existing)
    session.commit()
    return True


def channel_source_ids(session: Session, channel_id: str) -> list[str]:
    """Return the source ids linked to a channel."""
    return list(
        session.exec(
            select(ChannelSource.source_id).where(
                ChannelSource.channel_id == channel_id
            )
        ).all()
    )


__all__ = [
    "DEFAULT_CHANNEL_NAME",
    "DEFAULT_CHANNEL_SLUG",
    "channel_source_ids",
    "ensure_default_channel",
    "get_default_channel",
    "link_source",
    "slugify",
    "unlink_source",
]
