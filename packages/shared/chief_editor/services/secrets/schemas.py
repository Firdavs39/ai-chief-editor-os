"""Provider field schemas for the Integration Secrets Vault.

`is_secret` is **schema-derived only**, never persisted to the DB. Add a
provider here and it becomes saveable, gettable, testable, and deletable.

A `FieldSpec` lists everything the UI + resolver need to know about one
input field. Field values are always stored encrypted at rest; for fields
where `is_secret=False` the resolver and `safe_metadata` may still surface
the plaintext (URLs, model names) to the operator — that is by design.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    key_name: str
    label: str
    env_var: str
    is_secret: bool
    required: bool
    placeholder: str = ""
    docs_hint: str = ""
    # When True, the frontend hides this field under "Advanced settings".
    # Set for fields that the average operator should not need to touch
    # (custom endpoints, optional integration IDs, etc.).
    advanced: bool = False


@dataclass(frozen=True)
class ProviderSpec:
    provider: str
    label: str
    docs_anchor: str
    fields: tuple[FieldSpec, ...]

    def field(self, key_name: str) -> FieldSpec | None:
        for f in self.fields:
            if f.key_name == key_name:
                return f
        return None


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "ollama": ProviderSpec(
        provider="ollama",
        label="Ollama / Kimi K2.6",
        docs_anchor="docs/INTEGRATIONS.md#llm",
        fields=(
            # Required-and-primary: the API key. Most users only ever touch this.
            FieldSpec(
                "api_key",
                "Ollama API key",
                "OLLAMA_API_KEY",
                is_secret=True,
                required=False,
                placeholder="Paste your Ollama API key",
            ),
            # Visible primary, but auto-filled by the preset selector — operators
            # rarely change it.
            FieldSpec(
                "model",
                "Model",
                "OLLAMA_MODEL",
                is_secret=False,
                required=True,
                placeholder="kimi-k2.6:cloud",
            ),
            # Hidden under "Advanced endpoint settings". The preset selector
            # auto-fills this so most users never see the field.
            FieldSpec(
                "base_url",
                "Endpoint base URL",
                "OLLAMA_BASE_URL",
                is_secret=False,
                required=True,
                placeholder="https://ollama.com or http://localhost:11434/v1",
                advanced=True,
            ),
        ),
    ),
    "anthropic": ProviderSpec(
        provider="anthropic",
        label="Anthropic Claude",
        docs_anchor="docs/INTEGRATIONS.md#anthropic",
        fields=(
            FieldSpec(
                "api_key",
                "Anthropic API key",
                "ANTHROPIC_API_KEY",
                is_secret=True,
                required=True,
                placeholder="Paste your Anthropic API key",
            ),
            FieldSpec(
                "model",
                "Model",
                "ANTHROPIC_MODEL",
                is_secret=False,
                required=False,
                placeholder="claude-opus-4-7",
                advanced=True,
            ),
        ),
    ),
    "openai": ProviderSpec(
        provider="openai",
        label="OpenAI",
        docs_anchor="docs/INTEGRATIONS.md#openai",
        fields=(
            FieldSpec(
                "api_key",
                "OpenAI API key",
                "OPENAI_API_KEY",
                is_secret=True,
                required=True,
                placeholder="Paste your OpenAI API key",
            ),
            FieldSpec(
                "model",
                "Model",
                "OPENAI_MODEL",
                is_secret=False,
                required=False,
                placeholder="gpt-4o",
                advanced=True,
            ),
        ),
    ),
    "telegram_bot": ProviderSpec(
        provider="telegram_bot",
        label="Telegram Bot (publish)",
        docs_anchor="docs/INTEGRATIONS.md#telegram-publish",
        fields=(
            FieldSpec(
                "bot_token",
                "Bot token",
                "TELEGRAM_BOT_TOKEN",
                is_secret=True,
                required=True,
                placeholder="123456:ABC-DEF...",
            ),
            FieldSpec(
                "target_channel_id",
                "Target channel",
                "TELEGRAM_TARGET_CHANNEL_ID",
                is_secret=False,
                required=True,
                placeholder="@your_channel or -100...",
            ),
        ),
    ),
    "telethon": ProviderSpec(
        provider="telethon",
        label="Telethon (monitor)",
        docs_anchor="docs/INTEGRATIONS.md#telethon",
        fields=(
            FieldSpec(
                "api_id",
                "API ID",
                "TELETHON_API_ID",
                is_secret=True,
                required=True,
                placeholder="Numeric ID from my.telegram.org",
            ),
            FieldSpec(
                "api_hash",
                "API hash",
                "TELETHON_API_HASH",
                is_secret=True,
                required=True,
                placeholder="32-char hex hash",
            ),
        ),
    ),
    "reddit": ProviderSpec(
        provider="reddit",
        label="Reddit (read-only)",
        docs_anchor="docs/INTEGRATIONS.md#reddit",
        fields=(
            FieldSpec(
                "client_id",
                "Client ID",
                "REDDIT_CLIENT_ID",
                is_secret=True,
                required=True,
                placeholder="From reddit.com/prefs/apps",
            ),
            FieldSpec(
                "client_secret",
                "Client secret",
                "REDDIT_CLIENT_SECRET",
                is_secret=True,
                required=True,
                placeholder="Script app secret",
            ),
            FieldSpec(
                "user_agent",
                "User agent",
                "REDDIT_USER_AGENT",
                is_secret=False,
                required=False,
                placeholder="my-app/1.0 (by /u/me)",
                advanced=True,
            ),
        ),
    ),
    "postiz": ProviderSpec(
        provider="postiz",
        label="Postiz (Threads / Reddit publish)",
        docs_anchor="docs/INTEGRATIONS.md#postiz",
        fields=(
            FieldSpec(
                "base_url",
                "Base URL",
                "POSTIZ_BASE_URL",
                is_secret=False,
                required=True,
                placeholder="https://postiz.com",
            ),
            FieldSpec(
                "api_key",
                "Postiz API key",
                "POSTIZ_API_KEY",
                is_secret=True,
                required=True,
                placeholder="Paste your Postiz API token",
            ),
            FieldSpec(
                "threads_integration_id",
                "Threads integration ID",
                "POSTIZ_THREADS_INTEGRATION_ID",
                is_secret=False,
                required=False,
                placeholder="Optional — set to enable Threads publishing",
                advanced=True,
            ),
            FieldSpec(
                "reddit_integration_id",
                "Reddit integration ID",
                "POSTIZ_REDDIT_INTEGRATION_ID",
                is_secret=False,
                required=False,
                placeholder="Optional — set to enable Reddit-via-Postiz",
                advanced=True,
            ),
        ),
    ),
}


SUPPORTED_PROVIDERS: tuple[str, ...] = tuple(PROVIDER_SPECS.keys())


def get_provider_spec(provider: str) -> ProviderSpec:
    spec = PROVIDER_SPECS.get(provider)
    if spec is None:
        raise KeyError(provider)
    return spec
