"""Pick an LLM provider based on settings + vault, with sensible fallback to mock.

Env vars still take priority. If a real provider is selected but its env
keys are missing, the resolver checks the encrypted vault for a value
before falling back to the mock provider.
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


def get_llm_provider(force_mock: bool = False) -> LLMProvider:
    global _cached
    if _cached is not None and not force_mock:
        return _cached

    settings = get_settings()
    if force_mock or settings.mock_mode or settings.llm_provider == "mock":
        _cached = MockLLMProvider()
        return _cached

    if settings.llm_provider == "anthropic":
        # Env first.
        if settings.has_anthropic:
            from .anthropic_provider import AnthropicProvider

            _cached = AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model)
            return _cached
        # Vault fallback.
        resolved = resolve_provider("anthropic")
        api_key = resolved["api_key"].value
        if api_key:
            from .anthropic_provider import AnthropicProvider

            model = resolved["model"].value or settings.anthropic_model
            _cached = AnthropicProvider(api_key, model)
            return _cached
        log.warning("anthropic key missing (env+vault) — falling back to mock LLM")
        _cached = MockLLMProvider()
        return _cached

    if settings.llm_provider == "openai":
        if settings.has_openai:
            from .openai_provider import OpenAIProvider

            _cached = OpenAIProvider(settings.openai_api_key, settings.openai_model)
            return _cached
        resolved = resolve_provider("openai")
        api_key = resolved["api_key"].value
        if api_key:
            from .openai_provider import OpenAIProvider

            model = resolved["model"].value or settings.openai_model
            _cached = OpenAIProvider(api_key, model)
            return _cached
        log.warning("openai key missing (env+vault) — falling back to mock LLM")
        _cached = MockLLMProvider()
        return _cached

    if settings.llm_provider == "ollama":
        if settings.has_ollama:
            from .ollama_provider import OllamaProvider

            _cached = OllamaProvider(
                base_url=settings.ollama_base_url,
                api_key=settings.resolved_ollama_key(),
                model=settings.ollama_model,
            )
            return _cached
        # Vault fallback for Ollama.
        resolved = resolve_provider("ollama")
        base_url = resolved["base_url"].value or ""
        if base_url:
            from .ollama_provider import OllamaProvider

            api_key = resolved["api_key"].value or ""
            if not api_key and _is_ollama_local(base_url):
                api_key = "ollama"
            model = resolved["model"].value or settings.ollama_model
            if api_key:
                _cached = OllamaProvider(base_url=base_url, api_key=api_key, model=model)
                return _cached
        log.warning(
            "ollama config missing (env+vault) — falling back to mock LLM",
        )
        _cached = MockLLMProvider()
        return _cached

    log.warning("unknown LLM_PROVIDER=%s — falling back to mock", settings.llm_provider)
    _cached = MockLLMProvider()
    return _cached


def reset_provider_cache() -> None:
    global _cached
    _cached = None
