"""Application settings, loaded from env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["dev", "prod", "test"] = "dev"
    mock_mode: bool = True
    demo_mode: bool = True
    live_mode: bool = False
    dry_run_publish: bool = True
    publishing_enabled: bool = False
    worker_heartbeat_ttl_seconds: int = 120
    timezone: str = "Asia/Tashkent"

    database_url: str = "sqlite:///./chief_editor.db"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: Literal["mock", "anthropic", "openai", "ollama"] = "mock"
    # Phase 6: fallback provider used by the workflow when the primary
    # provider fails twice on the same step (i.e. original call + one
    # validation-aware repair both failed). Empty = no fallback (Phase 5
    # behaviour). Setting this to the SAME provider as `llm_provider` is
    # a no-op — the resolver short-circuits identical primary/fallback.
    llm_provider_fallback: Literal["", "mock", "anthropic", "openai", "ollama"] = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"
    openai_model: str = "gpt-4o"

    # Ollama / OpenAI-compatible (Kimi K2.6 via Ollama Cloud or local Ollama)
    ollama_base_url: str = ""
    ollama_api_key: str = ""
    ollama_model: str = "kimi-k2.6:cloud"

    telegram_bot_token: str = ""
    telegram_owner_id: str = ""
    telegram_target_channel_id: str = ""
    telethon_api_id: str = ""
    telethon_api_hash: str = ""
    telethon_session_name: str = "chief_editor_session"

    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ai-chief-editor-os-dev"

    postiz_base_url: str = ""
    postiz_api_key: str = ""
    postiz_threads_integration_id: str = ""
    postiz_reddit_integration_id: str = ""

    api_base_url: str = "http://localhost:8000"

    # Deployment-time identity
    frontend_origin: str = ""        # comma-separated CORS allow-list; empty = "*"
    public_api_url: str = ""         # the URL this API is reachable at (informational)

    # Integration Secrets Vault — see docs/SECRETS_VAULT.md
    master_encryption_key: str = ""              # primary Fernet key
    master_encryption_keys_legacy: str = ""      # comma-separated legacy keys (read-only)
    admin_token: str = ""                        # required on /secrets/* in any non-loopback context

    collect_interval_seconds: int = 300
    generate_interval_seconds: int = 600
    publish_interval_seconds: int = 30

    score_weights: dict[str, float] = {
        "recency": 0.20,
        "engagement": 0.20,
        "source_weight": 0.10,
        "novelty": 0.15,
        "controversy": 0.05,
        "usefulness": 0.15,
        "style_fit": 0.15,
    }

    @property
    def cors_origins(self) -> list[str]:
        """CORS allow-list parsed from `FRONTEND_ORIGIN`. Empty → ["*"] (dev only)."""
        raw = (self.frontend_origin or "").strip()
        if not raw:
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def is_ollama_local(self) -> bool:
        url = (self.ollama_base_url or "").lower()
        return any(
            host in url for host in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")
        )

    @property
    def has_ollama(self) -> bool:
        if not self.ollama_base_url:
            return False
        # Local Ollama does not require auth — a harmless default token is fine.
        return bool(self.ollama_api_key) or self.is_ollama_local

    def resolved_ollama_key(self) -> str:
        """Return the API key Ollama should be called with.

        For local Ollama (`localhost`/`127.0.0.1`) the value `ollama` is the
        documented sentinel that the local server accepts. This method never
        returns an empty string for a properly-configured local endpoint, and
        it never invents a key for a remote one.
        """
        if self.ollama_api_key:
            return self.ollama_api_key
        if self.is_ollama_local:
            return "ollama"
        return ""

    @property
    def has_telethon(self) -> bool:
        return bool(self.telethon_api_id and self.telethon_api_hash)

    @property
    def has_reddit(self) -> bool:
        return bool(self.reddit_client_id and self.reddit_client_secret)

    @property
    def has_telegram_publish(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_target_channel_id)

    @property
    def has_postiz(self) -> bool:
        return bool(self.postiz_base_url and self.postiz_api_key)

    @property
    def vault_enabled(self) -> bool:
        return bool(self.master_encryption_key)

    @property
    def legacy_encryption_keys(self) -> list[str]:
        raw = (self.master_encryption_keys_legacy or "").strip()
        if not raw:
            return []
        return [k.strip() for k in raw.split(",") if k.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
