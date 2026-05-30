"""Database engine + session helpers.

For file-backed SQLite (e.g. `sqlite:////data/chief_editor.db` on a Fly volume),
we enable WAL journal mode + NORMAL sync so the API + worker can write
concurrently from separate processes without `database is locked` errors.
This has no effect on Postgres or on `:memory:` SQLite.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from .settings import get_settings

_engine: Engine | None = None


def _enable_sqlite_pragmas(dbapi_connection, _) -> None:
    """Apply WAL + sensible defaults on every new SQLite connection."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cur = dbapi_connection.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=5000")
        finally:
            cur.close()


def _build_engine() -> Engine:
    settings = get_settings()
    url = settings.database_url

    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if ":memory:" in url:
            engine = create_engine(
                url,
                echo=False,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        else:
            engine = create_engine(url, echo=False, connect_args=connect_args)
        event.listen(engine, "connect", _enable_sqlite_pragmas)
        return engine

    return create_engine(url, echo=False, pool_pre_ping=True, pool_size=5, max_overflow=10)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def reset_engine() -> None:
    """Drop the cached engine. Used by tests."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def init_db() -> None:
    """Create all tables, then run the idempotent default-channel migration.

    Both steps are safe to repeat on every boot. The migration creates the
    default Channel, links existing sources, and backfills NULL channel FKs
    on runs/candidates so a single-channel deployment becomes multi-channel
    aware with no manual step.
    """
    # Importing models registers them with SQLModel.metadata.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())

    # Default-channel migration. Kept defensive: a migration failure must not
    # prevent the API/worker from booting (the per-channel code paths all fall
    # back to single-channel behaviour when no default channel exists).
    try:
        from .services.channels import (
            ensure_channel_columns,
            ensure_default_channel,
        )

        # ALTER pre-existing tables for the new channel_id columns BEFORE any
        # query touches them (create_all can't add columns to old tables).
        ensure_channel_columns(get_engine())

        with Session(get_engine()) as session:
            ensure_default_channel(session)
    except Exception:  # noqa: BLE001 — never block boot on the migration
        import logging

        logging.getLogger("chief_editor.db").warning(
            "default-channel migration skipped (will retry next boot)",
            exc_info=True,
        )


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    with Session(get_engine()) as session:
        yield session


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for use outside of FastAPI."""
    with Session(get_engine()) as session:
        yield session
