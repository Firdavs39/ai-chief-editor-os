"""Shared pytest fixtures — in-memory SQLite, fresh per test."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("packages/shared", "apps/api", "apps/worker"):
    p = str(ROOT / sub)
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("LLM_PROVIDER", "mock")

# Provide a deterministic MASTER_ENCRYPTION_KEY so vault-aware tests can run.
# Tests that need vault-disabled behavior monkeypatch this away and clear the
# Settings cache.
from cryptography.fernet import Fernet  # noqa: E402

os.environ.setdefault("MASTER_ENCRYPTION_KEY", Fernet.generate_key().decode())

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from chief_editor import db as db_module  # noqa: E402
from chief_editor.llm import registry as llm_registry  # noqa: E402
from chief_editor.settings import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    """Build a fresh in-memory engine per test and rebuild all tables."""
    get_settings.cache_clear()
    db_module.reset_engine()
    llm_registry.reset_provider_cache()
    engine = db_module.get_engine()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)
    db_module.reset_engine()


@pytest.fixture()
def session():
    with db_module.session_scope() as s:
        yield s


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
