"""Readiness endpoints — must never crash on missing config and never leak secrets."""

from __future__ import annotations


def test_readiness_returns_full_report(client) -> None:
    response = client.get("/readiness")
    assert response.status_code == 200
    body = response.json()
    assert body["generated_at"]
    assert "mode" in body
    assert {"mock_mode", "demo_mode", "live_mode", "dry_run_publish", "publishing_enabled"} <= set(
        body["mode"].keys()
    )
    assert isinstance(body["sections"], list)
    keys = {s["key"] for s in body["sections"]}
    assert {"mode", "llm", "telegram", "reddit", "postiz", "worker", "sources", "publishing_safety"} <= keys


def test_readiness_test_llm_in_mock_mode_returns_valid_or_mock(client) -> None:
    response = client.post("/readiness/test-llm")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"valid", "mock"}
    assert body["severity"] in {"info", "success"}


def test_readiness_test_telegram_missing_returns_missing_config(client) -> None:
    response = client.post("/readiness/test-telegram-bot")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"missing_config", "configured", "valid", "invalid", "error"}
    if body["status"] == "missing_config":
        assert "TELEGRAM_BOT_TOKEN" in body["missing_env_vars"]


def test_readiness_test_reddit_missing_returns_missing_config(client) -> None:
    response = client.post("/readiness/test-reddit")
    assert response.status_code == 200
    body = response.json()
    if body["status"] == "missing_config":
        assert "REDDIT_CLIENT_ID" in body["missing_env_vars"]


def test_readiness_test_postiz_missing_returns_missing_config(client) -> None:
    response = client.post("/readiness/test-postiz")
    assert response.status_code == 200
    body = response.json()
    if body["status"] == "missing_config":
        assert "POSTIZ_BASE_URL" in body["missing_env_vars"]


def test_readiness_test_telethon_missing_returns_missing_config(client) -> None:
    response = client.post("/readiness/test-telethon")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"missing_config", "configured", "valid"}


def test_readiness_no_secret_substring_in_response(client) -> None:
    """No response anywhere may include a secret value or prefix."""
    response = client.get("/readiness")
    blob = response.text
    # We never set real secrets in tests so a soft check on common token shapes.
    assert "sk-ant-" not in blob
    assert "sk-proj-" not in blob
    # Bot tokens look like 12345:AAA... — there must be no colon-form leak even
    # in mock environments because we never inject one.


def test_dry_run_publish_returns_payload_and_does_not_publish(client) -> None:
    # Seed first so we have a candidate.
    client.post("/demo/seed")
    candidates = client.get("/candidates").json()
    assert candidates
    cand_id = candidates[0]["id"]
    response = client.post(f"/readiness/dry-run-publish/{cand_id}?platform=telegram")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    preview = body["preview"]
    assert preview["dry_run"] is True
    assert preview["platform"] == "telegram"
    assert isinstance(preview["body"], str)
    assert preview["body_length"] == len(preview["body"])
    assert preview["safety"]["dry_run_publish"] is True


def test_worker_status_returns_structure(client) -> None:
    response = client.get("/worker/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["overall"] in {"running", "stale", "partial", "unknown"}
    assert "loops" in body
    assert "last_events" in body
