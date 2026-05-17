"""LLM provider registry — must never crash on missing env, must cache,
and must respect mock_mode precedence.
"""

from __future__ import annotations

from chief_editor.llm import registry as reg
from chief_editor.llm.mock import MockLLMProvider
from chief_editor.settings import get_settings


def _refresh() -> None:
    get_settings.cache_clear()
    reg.reset_provider_cache()


def test_registry_returns_mock_in_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    _refresh()
    provider = reg.get_llm_provider()
    assert isinstance(provider, MockLLMProvider), (
        "MOCK_MODE=true must take precedence even when a real key is set"
    )


def test_registry_falls_back_to_mock_when_anthropic_key_missing(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _refresh()
    provider = reg.get_llm_provider()
    assert isinstance(provider, MockLLMProvider)


def test_registry_falls_back_to_mock_when_openai_key_missing(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    _refresh()
    provider = reg.get_llm_provider()
    assert isinstance(provider, MockLLMProvider)


def test_registry_falls_back_to_mock_for_unknown_provider(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    # Settings has a Literal so we can't go via env easily — but the registry
    # itself must defend against any unexpected string. Validate via direct
    # function call.
    from chief_editor.settings import Settings

    s = Settings(_env_file=None, mock_mode=False, llm_provider="anthropic")
    monkeypatch.setattr(s, "llm_provider", "weird-value", raising=False)
    monkeypatch.setattr(reg, "get_settings", lambda: s, raising=False)
    reg.reset_provider_cache()
    provider = reg.get_llm_provider()
    assert isinstance(provider, MockLLMProvider)


def test_registry_caches_provider(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    _refresh()
    a = reg.get_llm_provider()
    b = reg.get_llm_provider()
    assert a is b


def test_registry_reset_invalidates_cache(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    _refresh()
    a = reg.get_llm_provider()
    reg.reset_provider_cache()
    b = reg.get_llm_provider()
    assert a is not b
    assert isinstance(b, MockLLMProvider)


def test_registry_force_mock_returns_mock_provider(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    _refresh()
    # Both calls must return a Mock provider. force_mock=True must not crash
    # even when something is already cached.
    assert isinstance(reg.get_llm_provider(), MockLLMProvider)
    assert isinstance(reg.get_llm_provider(force_mock=True), MockLLMProvider)
