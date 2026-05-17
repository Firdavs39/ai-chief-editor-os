"""HTTP-level tests for the /secrets/* router."""

from __future__ import annotations

import pytest
from sqlmodel import select

from chief_editor.models import IntegrationSecret, SystemLog
from chief_editor.settings import get_settings

PROD_TOKEN = "test-admin-token-do-not-leak"
HDR = {"X-Admin-Token": PROD_TOKEN}


@pytest.fixture()
def admin_client(client, monkeypatch):
    """Client with ADMIN_TOKEN set so write/test endpoints are unlocked."""
    monkeypatch.setenv("ADMIN_TOKEN", PROD_TOKEN)
    get_settings.cache_clear()
    yield client


def test_get_without_token_in_non_dev_mode_returns_401(client, monkeypatch) -> None:
    # Force non-loopback by changing app_env. ADMIN_TOKEN stays unset.
    monkeypatch.setenv("APP_ENV", "prod")
    get_settings.cache_clear()
    r = client.get("/secrets/integrations")
    assert r.status_code == 401


def test_get_with_token_returns_safe_list(admin_client) -> None:
    r = admin_client.get("/secrets/integrations", headers=HDR)
    assert r.status_code == 200
    body = r.json()
    assert "vault_enabled" in body
    providers = {p["provider"] for p in body["providers"]}
    assert {"ollama", "anthropic", "openai", "telegram_bot", "telethon", "reddit", "postiz"} <= providers
    # No stored secret value (or value hint with real bytes) appears in the
    # safe_metadata for any secret field — placeholders are static UI strings
    # not derived from any stored value, so they are explicitly allowed.
    for p in body["providers"]:
        for f in p["fields"]:
            if f["is_secret"]:
                assert "value" not in f["safe_metadata"]


def test_post_without_token_returns_401(client, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("ADMIN_TOKEN", "x")
    get_settings.cache_clear()
    r = client.post("/secrets/anthropic", json={"values": {"api_key": "sk-ant-xyz"}})
    assert r.status_code == 401


def test_post_with_wrong_token_returns_401(admin_client) -> None:
    r = admin_client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": "sk-ant-xyz"}},
        headers={"X-Admin-Token": "WRONG"},
    )
    assert r.status_code == 401


def test_post_stores_encrypted_value(admin_client, session) -> None:
    payload = "sk-ant-supersecret-1234567890"
    r = admin_client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": payload}},
        headers=HDR,
    )
    assert r.status_code == 200, r.text
    # Response must not echo plaintext.
    assert payload not in r.text

    row = session.exec(
        select(IntegrationSecret).where(
            IntegrationSecret.provider == "anthropic",
            IntegrationSecret.key_name == "api_key",
        )
    ).first()
    assert row is not None
    # The encrypted value must NOT contain the plaintext as a substring.
    assert payload not in row.encrypted_value


def test_post_response_returns_only_safe_metadata(admin_client) -> None:
    payload = "sk-ant-xyzabc-1234567890"
    r = admin_client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": payload}},
        headers=HDR,
    )
    body = r.json()
    api_field = next(f for f in body["fields"] if f["key_name"] == "api_key")
    assert api_field["safe_metadata"]["is_secret"] is True
    assert "value" not in api_field["safe_metadata"]
    assert "length" in api_field["safe_metadata"]
    assert payload not in r.text


def test_post_unknown_field_returns_400(admin_client) -> None:
    r = admin_client.post(
        "/secrets/anthropic",
        json={"values": {"bogus_key": "abc"}},
        headers=HDR,
    )
    assert r.status_code == 400


def test_post_empty_string_deletes_row(admin_client, session) -> None:
    # Seed a row first.
    admin_client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": "sk-ant-temp-12345"}},
        headers=HDR,
    )
    # Re-post with empty string for that key.
    r = admin_client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": ""}},
        headers=HDR,
    )
    assert r.status_code == 200
    row = session.exec(
        select(IntegrationSecret).where(
            IntegrationSecret.provider == "anthropic",
            IntegrationSecret.key_name == "api_key",
        )
    ).first()
    assert row is None


def test_delete_removes_row(admin_client) -> None:
    admin_client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": "sk-ant-delete-me-12345"}},
        headers=HDR,
    )
    r = admin_client.delete("/secrets/anthropic/api_key", headers=HDR)
    assert r.status_code == 200
    body = r.json()
    api_field = next(f for f in body["fields"] if f["key_name"] == "api_key")
    assert api_field["source"] == "missing"


def test_delete_unknown_provider_returns_404(admin_client) -> None:
    r = admin_client.delete("/secrets/nonexistent/api_key", headers=HDR)
    assert r.status_code == 404


def test_delete_unknown_key_name_returns_404(admin_client) -> None:
    r = admin_client.delete("/secrets/anthropic/bogus", headers=HDR)
    assert r.status_code == 404


def test_systemlog_data_never_contains_plaintext(admin_client, session) -> None:
    payload = "sk-ant-AUDITTEST-9988776655"
    admin_client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": payload}},
        headers=HDR,
    )
    admin_client.delete("/secrets/anthropic/api_key", headers=HDR)
    rows = list(session.exec(select(SystemLog)).all())
    # Some vault.* log rows must exist.
    vault_events = [r for r in rows if r.event.startswith("vault.")]
    assert vault_events, "expected vault audit events"
    # No row may include the plaintext value in any field.
    for r in rows:
        assert payload not in r.event
        assert payload not in r.message
        assert payload not in str(r.data)


def test_vault_disabled_blocks_writes(client, monkeypatch) -> None:
    # Empty string in os.environ wins over .env value.
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "")
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYS_LEGACY", "")
    monkeypatch.setenv("ADMIN_TOKEN", PROD_TOKEN)
    get_settings.cache_clear()
    r = client.post(
        "/secrets/anthropic",
        json={"values": {"api_key": "sk-ant-xyz"}},
        headers=HDR,
    )
    assert r.status_code == 409
    body = r.json()
    # Detail object carries the disabled status.
    assert body["detail"]["reason"] == "missing_master_key"


def test_test_endpoint_in_mock_mode_returns_safe_response(admin_client) -> None:
    # No keys configured; mock mode is on by default. Test endpoint should
    # not publish and should not 500.
    r = admin_client.post("/secrets/anthropic/test", headers=HDR)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"missing_config", "valid", "invalid", "error"}
    # Never include plaintext.
    assert "sk-ant-" not in r.text
