"""UX-shape tests for the Integrations Vault.

The frontend presets and Advanced collapsible are pure UI concerns, but the
backend has to (a) expose an `advanced` flag per field and (b) accept the
preset-shaped POST payloads exactly as the UI sends them. These tests pin
those contracts.

The 169 existing tests cover encryption, auth, resolution, and safety;
this file focuses on the new field contract.
"""

from __future__ import annotations

import pytest

from chief_editor.services.secrets import PROVIDER_SPECS, get_provider_spec
from chief_editor.settings import get_settings

PROD_TOKEN = "test-admin-token-ux"
HDR = {"X-Admin-Token": PROD_TOKEN}


@pytest.fixture()
def admin_client(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", PROD_TOKEN)
    get_settings.cache_clear()
    yield client


# ---------------------------------------------------------------------------
# Schema-level tests
# ---------------------------------------------------------------------------


def test_field_spec_carries_advanced_flag() -> None:
    spec = get_provider_spec("ollama")
    by_name = {f.key_name: f for f in spec.fields}
    assert by_name["base_url"].advanced is True
    assert by_name["api_key"].advanced is False
    assert by_name["model"].advanced is False


def test_anthropic_model_is_advanced_api_key_is_not() -> None:
    spec = get_provider_spec("anthropic")
    by_name = {f.key_name: f for f in spec.fields}
    assert by_name["api_key"].advanced is False
    assert by_name["model"].advanced is True


def test_all_specs_have_at_least_one_primary_field() -> None:
    """Every provider must surface at least one non-advanced field, else the
    Vault UI would render an empty primary section."""
    for provider, spec in PROVIDER_SPECS.items():
        primary = [f for f in spec.fields if not f.advanced]
        assert primary, f"provider {provider} has no primary fields"


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------


def test_api_response_includes_advanced_flag(admin_client) -> None:
    r = admin_client.get("/secrets/ollama", headers=HDR)
    assert r.status_code == 200
    body = r.json()
    by_name = {f["key_name"]: f for f in body["fields"]}
    assert by_name["base_url"]["advanced"] is True
    assert by_name["api_key"]["advanced"] is False
    assert by_name["model"]["advanced"] is False


def test_field_order_keeps_advanced_visible_but_not_first(admin_client) -> None:
    r = admin_client.get("/secrets/ollama", headers=HDR)
    fields = r.json()["fields"]
    # The schema lists api_key + model as primary first, base_url advanced last.
    assert fields[0]["key_name"] == "api_key"
    assert fields[-1]["key_name"] == "base_url"
    assert fields[-1]["advanced"] is True


# ---------------------------------------------------------------------------
# Preset-shaped saves
# ---------------------------------------------------------------------------


def test_ollama_cloud_preset_save(admin_client) -> None:
    """Frontend Ollama Cloud preset sends base_url=https://ollama.com and
    model=kimi-k2.6:cloud along with the user-typed api_key."""
    r = admin_client.post(
        "/secrets/ollama",
        json={
            "values": {
                "base_url": "https://ollama.com",
                "api_key": "ollama-cloud-test-key-xyz-12345",
                "model": "kimi-k2.6:cloud",
            }
        },
        headers=HDR,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    by_name = {f["key_name"]: f for f in body["fields"]}
    # Non-secret fields surface their value in safe_metadata.
    assert by_name["base_url"]["safe_metadata"].get("value") == "https://ollama.com"
    assert by_name["model"]["safe_metadata"].get("value") == "kimi-k2.6:cloud"
    # Secret stays masked.
    assert by_name["api_key"]["safe_metadata"].get("is_secret") is True
    assert "value" not in by_name["api_key"]["safe_metadata"]
    # No plaintext anywhere in the response.
    assert "ollama-cloud-test-key-xyz-12345" not in r.text


def test_ollama_local_preset_save(admin_client) -> None:
    """Local preset uses /v1-style base_url and no api_key."""
    r = admin_client.post(
        "/secrets/ollama",
        json={
            "values": {
                "base_url": "http://localhost:11434/v1",
                "model": "kimi-k2.6:cloud",
            }
        },
        headers=HDR,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    by_name = {f["key_name"]: f for f in body["fields"]}
    assert by_name["base_url"]["safe_metadata"].get("value") == "http://localhost:11434/v1"
    assert by_name["model"]["safe_metadata"].get("value") == "kimi-k2.6:cloud"
    # api_key was NOT included → row absent → source missing.
    assert by_name["api_key"]["source"] == "missing"


def test_advanced_field_override_still_works(admin_client) -> None:
    """User opening Advanced and pasting a custom base_url overwrites the preset."""
    admin_client.post(
        "/secrets/ollama",
        json={
            "values": {
                "base_url": "https://ollama.com",
                "api_key": "first-key-1234567890",
                "model": "kimi-k2.6:cloud",
            }
        },
        headers=HDR,
    )
    r = admin_client.post(
        "/secrets/ollama",
        json={"values": {"base_url": "http://my-custom-ollama.example.com:11434"}},
        headers=HDR,
    )
    assert r.status_code == 200
    body = r.json()
    by_name = {f["key_name"]: f for f in body["fields"]}
    assert (
        by_name["base_url"]["safe_metadata"].get("value")
        == "http://my-custom-ollama.example.com:11434"
    )
    # The other fields stayed put.
    assert by_name["api_key"]["source"] == "vault"
    assert by_name["model"]["safe_metadata"].get("value") == "kimi-k2.6:cloud"


def test_save_partial_field_set_keeps_other_rows(admin_client, session) -> None:
    """Saving only api_key must not delete previously stored base_url/model.

    We assert directly against the DB because `OLLAMA_MODEL` has a non-empty
    Settings default (`kimi-k2.6:cloud`) and therefore the resolver reports
    `source=env` for it regardless of whether a vault row exists. Row
    persistence is the actual invariant we care about.
    """
    from sqlmodel import select

    from chief_editor.models import IntegrationSecret

    admin_client.post(
        "/secrets/ollama",
        json={
            "values": {
                "base_url": "https://ollama.com",
                "model": "kimi-k2.6:cloud",
            }
        },
        headers=HDR,
    )
    admin_client.post(
        "/secrets/ollama",
        json={"values": {"api_key": "later-arrived-key-1234567890"}},
        headers=HDR,
    )
    rows = list(
        session.exec(
            select(IntegrationSecret).where(IntegrationSecret.provider == "ollama")
        ).all()
    )
    keys = {r.key_name for r in rows}
    assert keys == {"base_url", "model", "api_key"}


# ---------------------------------------------------------------------------
# Safety: presets do not unlock publishing
# ---------------------------------------------------------------------------


def test_preset_save_does_not_create_approval_or_publish_job(admin_client, session) -> None:
    from sqlmodel import select

    from chief_editor.models import ApprovalDecision, PublishJob

    admin_client.post(
        "/secrets/ollama",
        json={
            "values": {
                "base_url": "https://ollama.com",
                "api_key": "preset-test-key-xyz-1234567890",
                "model": "kimi-k2.6:cloud",
            }
        },
        headers=HDR,
    )
    admin_client.post("/secrets/ollama/test", headers=HDR)
    assert session.exec(select(ApprovalDecision)).all() == []
    assert session.exec(select(PublishJob)).all() == []
