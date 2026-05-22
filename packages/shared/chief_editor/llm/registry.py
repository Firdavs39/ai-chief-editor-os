"""Pick an LLM provider based on settings + vault, with sensible fallback to mock.

Env vars still take priority. If a real provider is selected but its env
keys are missing, the resolver checks the encrypted vault for a value
before falling back to the mock provider.

Phase 6: `get_fallback_llm_provider()` returns a SECONDARY provider when
`LLM_PROVIDER_FALLBACK` is set and different from the primary. The
workflow uses it after the primary fails its own retry. Cost: one extra
LLM call on already-failing steps, only when the operator explicitly
enabled it.
"""

from __future__ import annotations

import logging

from ..services.integration_config import resolve_provider
from ..settings import get_settings
from .base import LLMProvider
from .mock import MockLLMProvider

log = logging.getLogger(__name__)

_cached: LLMProvider | None = None


def _is_ollama_local(base_url: str) -> bool:
    url = (base_url or "").lower()
    return any(
        host in url for host in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")
    )


def _build_provider(name: str) -> LLMProvider | None:
    """Construct one provider by name, consulting env then vault.

    Returns None when the named provider is "" / unknown / unconfigurable.
    Callers (the primary resolver, the fallback resolver) decide whether
    to fall back further to mock when this returns None.
    """
    settings = get_settings()

    if name == "" or name is None:
        return None

    if name == "mock":
        return MockLLMProvider()

    if name == "anthropic":
        if settings.has_anthropic:
            from .anthropic_provider import AnthropicProvider

            return AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
        resolved = resolve_provider("anthropic")
        api_key = resolved["api_key"].value
        if api_key:
            from .anthropic_provider import AnthropicProvider

            model = resolved["model"].value or settings.anthropic_model
            return AnthropicProvider(api_key, model)
        return None

    if name == "openai":
        if settings.has_openai:
            from .openai_provider import OpenAIProvider

            return OpenAIProvider(settings.openai_api_key, settings.openai_model)
        resolved = resolve_provider("openai")
        api_key = resolved["api_key"].value
        if api_key:
            from .openai_provider import OpenAIProvider

            model = resolved["model"].value or settings.openai_model
            return OpenAIProvider(api_key, model)
        return None

    if name == "ollama":
        if settings.has_ollama:
            from .ollama_provider import OllamaProvider

            return OllamaProvider(
                base_url=settings.ollama_base_url,
                api_key=settings.resolved_ollama_key(),
                model=settings.ollama_model,
            )
        resolved = resolve_provider("ollama")
        base_url = resolved["base_url"].value or ""
        if base_url:
            api_key = resolved["api_key"].value or ""
            if not api_key and _is_ollama_local(base_url):
                api_key = "ollama"
            model = resolved["model"].value or settings.ollama_model
            if api_key:
                from .ollama_provider import OllamaProvider

                return OllamaProvider(base_url=base_url, api_key=api_key, model=model)
        return None

    log.warning("unknown LLM provider name=%s", name)
    return None


def get_llm_provider(force_mock: bool = False) -> LLMProvider:
    global _cached
    if _cached is not None and not force_mock:
        return _cached

    settings = get_settings()
    if force_mock or settings.mock_mode:
        _cached = MockLLMProvider()
        return _cached

    primary = _build_provider(settings.llm_provider)
    if primary is None:
        log.warning(
            "primary LLM provider=%s not configured (env+vault) — falling back to mock",
            settings.llm_provider,
        )
        _cached = MockLLMProvider()
    else:
        _cached = primary
    return _cached


def get_fallback_llm_provider() -> LLMProvider | None:
    """Return the configured fallback provider, or None.

    Returns None when:
    - `LLM_PROVIDER_FALLBACK` is empty (the default — no fallback).
    - The fallback name equals the primary name (no point retrying the
      same provider — its own validation-aware repair already fired).
    - The fallback is configured but its credentials are missing.

    The fallback is NOT cached. It's a slow path and we want each call to
    re-read settings in case the vault changed mid-session.
    """
    settings = get_settings()
    fallback_name = settings.llm_provider_fallback or ""
    if not fallback_name:
        return None
    if fallback_name == settings.llm_provider:
        # Same as primary → not a fallback. Defensive guard.
        return None
    provider = _build_provider(fallback_name)
    if provider is None:
        log.warning(
            "LLM_PROVIDER_FALLBACK=%s requested but not configured (env+vault)",
            fallback_name,
        )
    return provider


def reset_provider_cache() -> None:
    global _cached
    _cached = None
