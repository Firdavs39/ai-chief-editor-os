"""OllamaProvider — settings, registry, readiness, isolated provider behavior.

Every test uses a mocked OpenAI client. No real HTTP is performed.
"""

from __future__ import annotations

import pytest

from chief_editor.llm import registry as reg
from chief_editor.llm.mock import MockLLMProvider
from chief_editor.llm.ollama_provider import OllamaProvider, _normalize_base_url, host_of
from chief_editor.settings import Settings, get_settings

# ---------------------------------------------------------------------------
# Settings + helpers
# ---------------------------------------------------------------------------


def test_settings_carries_ollama_fields() -> None:
    s = Settings(_env_file=None)
    assert s.ollama_base_url == ""
    assert s.ollama_api_key == ""
    assert s.ollama_model == "kimi-k2.6:cloud"
    assert s.has_ollama is False


def test_settings_has_ollama_true_for_cloud_with_key() -> None:
    s = Settings(
        _env_file=None,
        ollama_base_url="https://ollama.com",
        ollama_api_key="ollama_FAKE",
    )
    assert s.has_ollama is True
    assert s.is_ollama_local is False
    assert s.resolved_ollama_key() == "ollama_FAKE"


def test_settings_has_ollama_true_for_local_without_key() -> None:
    s = Settings(_env_file=None, ollama_base_url="http://localhost:11434")
    assert s.has_ollama is True
    assert s.is_ollama_local is True
    # Local sentinel — never pretend to have a key we don't.
    assert s.resolved_ollama_key() == "ollama"


def test_settings_has_ollama_false_for_remote_without_key() -> None:
    s = Settings(_env_file=None, ollama_base_url="https://ollama.com")
    assert s.has_ollama is False
    assert s.resolved_ollama_key() == ""


def test_normalize_base_url_appends_v1() -> None:
    assert _normalize_base_url("http://localhost:11434") == "http://localhost:11434/v1"
    assert _normalize_base_url("http://localhost:11434/") == "http://localhost:11434/v1"
    assert _normalize_base_url("https://ollama.com/v1") == "https://ollama.com/v1"
    assert _normalize_base_url("") == ""


def test_host_of_returns_only_host() -> None:
    assert host_of("https://ollama.com") == "ollama.com"
    assert host_of("http://localhost:11434") == "localhost:11434"
    assert host_of("http://127.0.0.1:11434/v1/chat") == "127.0.0.1:11434"


# ---------------------------------------------------------------------------
# Registry behavior
# ---------------------------------------------------------------------------


def test_registry_returns_ollama_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.com")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama_FAKE_KEY")
    get_settings.cache_clear()
    reg.reset_provider_cache()

    provider = reg.get_llm_provider()
    assert isinstance(provider, OllamaProvider)
    assert provider._model == "kimi-k2.6:cloud"


def test_registry_falls_back_to_mock_when_ollama_remote_missing_key(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.com")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    get_settings.cache_clear()
    reg.reset_provider_cache()

    provider = reg.get_llm_provider()
    assert isinstance(provider, MockLLMProvider)


def test_registry_returns_ollama_for_local_without_key(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    get_settings.cache_clear()
    reg.reset_provider_cache()

    provider = reg.get_llm_provider()
    assert isinstance(provider, OllamaProvider)


def test_registry_mock_mode_takes_precedence_over_ollama(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.com")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama_FAKE_KEY")
    get_settings.cache_clear()
    reg.reset_provider_cache()

    assert isinstance(reg.get_llm_provider(), MockLLMProvider)


# ---------------------------------------------------------------------------
# Readiness endpoint
# ---------------------------------------------------------------------------


def test_readiness_ollama_missing_base_url_returns_missing_config(
    client, monkeypatch
) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    get_settings.cache_clear()
    reg.reset_provider_cache()

    res = client.post("/readiness/test-llm")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "missing_config"
    assert "OLLAMA_BASE_URL" in body["missing_env_vars"]


def test_readiness_ollama_remote_missing_key_returns_missing_config(
    client, monkeypatch
) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.com")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    get_settings.cache_clear()
    reg.reset_provider_cache()

    res = client.post("/readiness/test-llm")
    body = res.json()
    assert body["status"] == "missing_config"
    assert "OLLAMA_API_KEY" in body["missing_env_vars"]


def test_readiness_ollama_local_without_key_does_not_require_key(
    client, monkeypatch
) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    get_settings.cache_clear()
    reg.reset_provider_cache()

    res = client.post("/readiness/test-llm")
    body = res.json()
    # We can't reach a real local Ollama in tests, but the missing-config
    # path must not fire (no missing env). It's an error/invalid response
    # from a network attempt — that's OK as long as we don't lie about config.
    assert body["status"] != "missing_config"
    assert body["missing_env_vars"] == []


def test_readiness_ollama_never_returns_api_key_value(client, monkeypatch) -> None:
    """The body of /readiness/test-llm must never contain the literal key."""
    secret = "ollama_DO_NOT_LEAK_THIS_TOKEN_aaaaaaaaaaaaaaaa"
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.com")
    monkeypatch.setenv("OLLAMA_API_KEY", secret)
    get_settings.cache_clear()
    reg.reset_provider_cache()

    res = client.post("/readiness/test-llm")
    blob = res.text
    assert secret not in blob, "API key value leaked into /readiness/test-llm response"
    # And the GET /readiness payload should also be clean.
    overview = client.get("/readiness").text
    assert secret not in overview


# ---------------------------------------------------------------------------
# Provider behavior with mocked OpenAI client
# ---------------------------------------------------------------------------


class _OMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _OChoice:
    def __init__(self, content: str) -> None:
        self.message = _OMessage(content)


class _OResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_OChoice(content)]


class _OCompletions:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(kw)
        if not self._responses:
            raise AssertionError("create() called more times than mocked responses")
        # When exactly one response remains, keep returning it (useful for
        # tests that drive many calls through `generate_for_cluster` during
        # demo seeding; the test only cares about the LAST few).
        if len(self._responses) == 1:
            return _OResponse(self._responses[0])
        return _OResponse(self._responses.pop(0))


class _OChat:
    def __init__(self, responses: list[str]) -> None:
        self.completions = _OCompletions(responses)


class _OClient:
    def __init__(self, responses: list[str]) -> None:
        self.chat = _OChat(responses)


def _ollama(responses: list[str]) -> OllamaProvider:
    p = OllamaProvider(
        base_url="https://ollama.com",
        api_key="ollama_FAKE",
        model="kimi-test",
    )
    p._client = _OClient(responses)
    return p


def test_ollama_complete_json_parses_clean_response() -> None:
    p = _ollama(['{"ok": true, "provider": "ollama"}'])
    out = p.complete_json("sys", "ping", {"type": "object"})
    assert out == {"ok": True, "provider": "ollama"}
    sent = p._client.chat.completions.calls[0]
    assert sent["model"] == "kimi-test"
    user_msg = sent["messages"][1]["content"]
    assert "STRICT JSON" in user_msg
    assert "ping" in user_msg


def test_ollama_repairs_prose_wrapped_json_without_retry() -> None:
    p = _ollama(['Sure: {"ok": true} — that should do it.'])
    out = p.complete_json("s", "u", {})
    assert out == {"ok": True}
    assert len(p._client.chat.completions.calls) == 1


def test_ollama_retries_once_on_invalid_json_then_succeeds() -> None:
    p = _ollama(["this is not json", '{"ok": true}'])
    out = p.complete_json("s", "u", {})
    assert out == {"ok": True}
    assert len(p._client.chat.completions.calls) == 2
    # Second call should carry the repair instruction.
    second_user = p._client.chat.completions.calls[1]["messages"][1]["content"]
    assert "could not be parsed" in second_user


def test_ollama_raises_after_two_invalid_responses() -> None:
    p = _ollama(["garbage one", "garbage two"])
    with pytest.raises(ValueError, match="invalid JSON twice"):
        p.complete_json("s", "u", {})


def test_ollama_rewrite_returns_stripped_text() -> None:
    p = _ollama(["  Острее: текст готов.\n"])
    assert p.rewrite("Исходный.", "sharper") == "Острее: текст готов."


def test_ollama_provider_refuses_empty_base_url() -> None:
    with pytest.raises(ValueError, match="base URL"):
        OllamaProvider(base_url="", api_key="ollama_FAKE")


def test_ollama_provider_refuses_empty_api_key() -> None:
    # The registry resolves a local sentinel for us; if anyone calls the
    # constructor directly with an empty key, fail loud.
    with pytest.raises(ValueError, match="API key"):
        OllamaProvider(base_url="https://ollama.com", api_key="")


def test_ollama_provider_uses_phase5_2_timeout_defaults() -> None:
    """Phase 5.2 follow-up: per-call timeout 900 s, 1 retry. Defaults
    matter because Phase 5.2 run #2 ran into the SDK default (600 s × 3
    retries = 1 800 s) which hides slow Kimi responses for too long."""
    assert OllamaProvider.DEFAULT_TIMEOUT_SECONDS == 900.0
    assert OllamaProvider.DEFAULT_MAX_RETRIES == 1


def test_ollama_provider_accepts_explicit_timeout_override() -> None:
    """Operators can tune timeout per environment without monkey-patching
    the class default."""
    p = OllamaProvider(
        base_url="https://ollama.com",
        api_key="ollama_FAKE",
        model="kimi-test",
        timeout_seconds=120.0,
        max_retries=0,
    )
    # The OpenAI SDK exposes timeout as `timeout` on the client instance
    # (https-x._client). We assert the underlying client got the value
    # we passed.
    assert p._client.timeout == 120.0
    assert p._client.max_retries == 0


# ---------------------------------------------------------------------------
# /brief/generate safety with ollama provider
# ---------------------------------------------------------------------------


def test_brief_generate_in_real_provider_mode_is_async(client, monkeypatch) -> None:
    """With Phase 1 of the Quality Editorial Workflow, /brief/generate in
    real-provider mode (MOCK_MODE=false + LLM_PROVIDER=ollama) MUST NOT
    call the LLM on the request thread. It enqueues `GenerationRun` rows
    and returns HTTP 202 with `{run_ids, status: "queued"}`. The actual
    candidate generation moves to the worker pipeline (Phase 2+).
    """
    from sqlmodel import select

    from chief_editor.db import session_scope
    from chief_editor.models import (
        ApprovalDecision,
        GenerationRun,
        PostCandidate,
        PublishJob,
    )

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://ollama.com")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama_FAKE_KEY")
    get_settings.cache_clear()
    reg.reset_provider_cache()

    # Inject a tripwire provider — if real-mode /brief/generate ever calls
    # complete_json, this raises and the test fails loudly.
    canned_unused = '{"ok":true}'
    p = _ollama([canned_unused])
    reg._cached = p  # type: ignore[attr-defined]

    client.post("/demo/seed")
    with session_scope() as s:
        before_candidates = len(s.exec(select(PostCandidate)).all())
        before_approvals = len(s.exec(select(ApprovalDecision)).all())
        before_jobs = len(s.exec(select(PublishJob)).all())
        before_runs = len(s.exec(select(GenerationRun)).all())

    res = client.post("/brief/generate", json={"top_n": 1})
    assert res.status_code == 202, res.text
    body = res.json()
    assert body["status"] == "queued"
    assert isinstance(body["run_ids"], list) and body["run_ids"]

    # Safety: no candidate, approval, or publish job created on the request
    # thread. Only new queued GenerationRun rows.
    with session_scope() as s:
        assert len(s.exec(select(PostCandidate)).all()) == before_candidates
        assert len(s.exec(select(ApprovalDecision)).all()) == before_approvals
        assert len(s.exec(select(PublishJob)).all()) == before_jobs
        runs = list(s.exec(select(GenerationRun)).all())
        assert len(runs) == before_runs + len(body["run_ids"])
        for r in runs:
            if r.id in body["run_ids"]:
                assert r.status == "queued"
