"""Safety invariants for the Integration Secrets Vault.

Validates that:
- Test endpoints never publish.
- Test endpoints never flip safety flags.
- /brief/generate remains draft-only.
- No ApprovalDecision or PublishJob is created by secret tests.
- The admin-token gate's strict-local-dev exemption fires only under safe
  conditions.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from sqlmodel import select

from chief_editor.models import ApprovalDecision, PublishJob, PublishResult
from chief_editor.settings import get_settings

TOKEN = "safety-test-token-9999"
HDR = {"X-Admin-Token": TOKEN}


def _set_admin(monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    get_settings.cache_clear()


def test_test_endpoint_does_not_publish(client, session, monkeypatch) -> None:
    _set_admin(monkeypatch)
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()

    with (
        patch("chief_editor.publishing.telegram.TelegramPublisher._dispatch") as tg,
        patch("chief_editor.publishing.postiz.PostizPublisher._dispatch") as pz,
    ):
        for provider in [
            "ollama",
            "anthropic",
            "openai",
            "telegram_bot",
            "telethon",
            "reddit",
            "postiz",
        ]:
            r = client.post(f"/secrets/{provider}/test", headers=HDR)
            assert r.status_code == 200, f"{provider}: {r.status_code} {r.text[:200]}"
        assert tg.call_count == 0
        assert pz.call_count == 0

    # No ApprovalDecision/PublishJob/PublishResult rows were created.
    assert session.exec(select(ApprovalDecision)).all() == []
    assert session.exec(select(PublishJob)).all() == []
    assert session.exec(select(PublishResult)).all() == []


def test_test_endpoint_keeps_safety_flags_unchanged(client, monkeypatch) -> None:
    _set_admin(monkeypatch)
    monkeypatch.setenv("PUBLISHING_ENABLED", "false")
    monkeypatch.setenv("DRY_RUN_PUBLISH", "true")
    get_settings.cache_clear()

    client.post("/secrets/anthropic/test", headers=HDR)

    s = get_settings()
    assert s.publishing_enabled is False
    assert s.dry_run_publish is True


def test_brief_generate_remains_draft_only(client, monkeypatch) -> None:
    _set_admin(monkeypatch)
    client.post("/demo/seed")
    r = client.post("/brief/generate", json={"top_n": 1})
    assert r.status_code == 200
    body = r.json()
    if body:
        for c in body:
            assert c["status"] == "draft"


def test_admin_token_required_in_prod(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ADMIN_TOKEN", "")
    get_settings.cache_clear()
    r = client.get("/secrets/integrations")
    assert r.status_code == 401


def test_admin_token_required_when_live_mode_on(client, monkeypatch) -> None:
    # Even in dev, LIVE_MODE=true forbids the no-token exemption.
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("LIVE_MODE", "true")
    monkeypatch.setenv("ADMIN_TOKEN", "")
    get_settings.cache_clear()
    r = client.get("/secrets/integrations")
    assert r.status_code == 401


def test_admin_token_required_when_public_api_url_set(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("LIVE_MODE", "false")
    monkeypatch.setenv("PUBLIC_API_URL", "https://api.example.com")
    monkeypatch.setenv("ADMIN_TOKEN", "")
    get_settings.cache_clear()
    r = client.get("/secrets/integrations")
    assert r.status_code == 401


def test_wrong_token_rejected_with_constant_behavior(client, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_TOKEN", "correct-token-9999")
    get_settings.cache_clear()
    r1 = client.get("/secrets/integrations", headers={"X-Admin-Token": "wrong-token-x"})
    r2 = client.get("/secrets/integrations", headers={"X-Admin-Token": ""})
    r3 = client.get("/secrets/integrations")
    assert r1.status_code == r2.status_code == r3.status_code == 401


def test_no_secret_substring_in_systemlog_after_full_cycle(client, session, monkeypatch) -> None:
    _set_admin(monkeypatch)
    payload = "TG-BOT-TOKEN-VALUE-987654321:ABC"
    client.post(
        "/secrets/telegram_bot",
        json={"values": {"bot_token": payload, "target_channel_id": "@x"}},
        headers=HDR,
    )
    client.post("/secrets/telegram_bot/test", headers=HDR)
    client.delete("/secrets/telegram_bot/bot_token", headers=HDR)

    from chief_editor.models import SystemLog

    rows = list(session.exec(select(SystemLog)).all())
    for r in rows:
        assert payload not in r.event
        assert payload not in r.message
        # JSON-serialize data and search for the literal payload.
        data_blob = json.dumps(r.data, ensure_ascii=False)
        assert payload not in data_blob, f"plaintext leak in {r.event}"


def test_readiness_response_never_contains_plaintext(client, session, monkeypatch) -> None:
    _set_admin(monkeypatch)
    payload = "sk-ant-readiness-leak-test-12345"
    client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": payload}},
        headers=HDR,
    )
    r = client.get("/readiness")
    assert payload not in r.text
