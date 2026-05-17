"""Env-vs-vault resolution behavior."""

from __future__ import annotations

from chief_editor.llm import registry as llm_registry
from chief_editor.models import IntegrationSecret
from chief_editor.services.integration_config import resolve_field, resolve_provider
from chief_editor.services.secrets import encrypt, safe_metadata_for
from chief_editor.settings import get_settings


def _seed(session, provider: str, key_name: str, value: str, *, is_secret: bool = True) -> None:
    session.add(
        IntegrationSecret(
            provider=provider,
            key_name=key_name,
            encrypted_value=encrypt(value),
            safe_metadata=safe_metadata_for(value, is_secret=is_secret),
            status="configured",
        )
    )
    session.commit()


def test_env_wins_over_vault(monkeypatch, session) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-value-wins")
    get_settings.cache_clear()
    _seed(session, "anthropic", "api_key", "vault-value-loses")

    field = resolve_field("anthropic", "api_key", session=session)
    assert field.value == "env-value-wins"
    assert field.source == "env"


def test_vault_used_when_env_missing(monkeypatch, session) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    _seed(session, "anthropic", "api_key", "vault-supplied-key")

    field = resolve_field("anthropic", "api_key", session=session)
    assert field.value == "vault-supplied-key"
    assert field.source == "vault"


def test_both_missing_returns_missing(monkeypatch, session) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    field = resolve_field("anthropic", "api_key", session=session)
    assert field.value is None
    assert field.source == "missing"


def test_resolve_provider_returns_all_fields(monkeypatch, session) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    get_settings.cache_clear()
    _seed(session, "ollama", "base_url", "https://ollama.com", is_secret=False)
    _seed(session, "ollama", "api_key", "ollama-cloud-key")
    resolved = resolve_provider("ollama", session=session)
    assert resolved["base_url"].value == "https://ollama.com"
    assert resolved["base_url"].source == "vault"
    assert resolved["api_key"].value == "ollama-cloud-key"
    # The default OLLAMA_MODEL is set on Settings, so resolver returns "env".
    assert resolved["model"].source == "env"


def test_llm_registry_uses_vault_when_env_missing(monkeypatch, session) -> None:
    # Anthropic env empty, vault has key, MOCK_MODE off, LLM_PROVIDER=anthropic.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()
    llm_registry.reset_provider_cache()

    _seed(session, "anthropic", "api_key", "sk-ant-vault-only-1234567890")

    # Build provider; we should get the real AnthropicProvider, not MockLLMProvider.
    provider = llm_registry.get_llm_provider()
    assert type(provider).__name__ == "AnthropicProvider"


def test_mock_mode_overrides_vault(monkeypatch, session) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    get_settings.cache_clear()
    llm_registry.reset_provider_cache()

    _seed(session, "anthropic", "api_key", "sk-ant-should-be-ignored-1234567890")

    provider = llm_registry.get_llm_provider()
    assert type(provider).__name__ == "MockLLMProvider"


def test_ollama_resolved_from_vault_when_env_missing(monkeypatch, session) -> None:
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()
    llm_registry.reset_provider_cache()

    _seed(session, "ollama", "base_url", "https://ollama.com", is_secret=False)
    _seed(session, "ollama", "api_key", "ollama-key")

    provider = llm_registry.get_llm_provider()
    assert type(provider).__name__ == "OllamaProvider"


def test_decrypt_failure_downgrades_to_missing(monkeypatch, session) -> None:
    # Seed a row encrypted with the active key, then rotate the env key so the
    # row becomes undecryptable. Resolver must not raise — it returns missing.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    _seed(session, "anthropic", "api_key", "rotateable-secret")

    from cryptography.fernet import Fernet
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("MASTER_ENCRYPTION_KEYS_LEGACY", raising=False)
    get_settings.cache_clear()

    field = resolve_field("anthropic", "api_key", session=session)
    assert field.source == "missing"
    assert field.value is None
