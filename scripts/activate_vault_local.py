"""One-shot helper to activate the Integration Secrets Vault locally.

Generates a fresh MASTER_ENCRYPTION_KEY via the project CLI, generates a
fresh ADMIN_TOKEN, and writes both into .env alongside the live-mode
settings already in use by the running API. Prints ONLY the ADMIN_TOKEN
(so the operator can paste it into the Settings → Integrations vault
unlock form). Never prints the master key.

Run from the project root:
    python scripts/activate_vault_local.py
"""

from __future__ import annotations

import secrets as stdlib_secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"

DESIRED_FLAGS = {
    "APP_ENV": "prod",
    "DEMO_MODE": "false",
    "LIVE_MODE": "true",
    "MOCK_MODE": "true",  # stays true until Ollama is configured + tested
    "DRY_RUN_PUBLISH": "true",
    "PUBLISHING_ENABLED": "false",
    "DATABASE_URL": "sqlite:///./chief_editor_live.db",
    "REDIS_URL": "redis://localhost:6379/0",
    "LLM_PROVIDER": "mock",  # flipped to ollama once vault has those secrets
    "TIMEZONE": "Asia/Tashkent",
    "WORKER_HEARTBEAT_TTL_SECONDS": "120",
    "API_BASE_URL": "http://localhost:8000",
    "NEXT_PUBLIC_API_URL": "http://localhost:8000",
}


def _generate_master_key() -> str:
    """Invoke the project CLI; capture stdout, do not print."""
    result = subprocess.run(
        [sys.executable, "-m", "chief_editor.services.secrets", "generate-key"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=True,
    )
    return result.stdout.strip()


def _generate_admin_token() -> str:
    return stdlib_secrets.token_urlsafe(32)


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v
    return out


def _write_env(path: Path, kv: dict[str, str]) -> None:
    # Preserve ordering: required flags first, then any extras alphabetically.
    ordered_keys: list[str] = []
    for k in (
        "APP_ENV",
        "MOCK_MODE",
        "DEMO_MODE",
        "LIVE_MODE",
        "DRY_RUN_PUBLISH",
        "PUBLISHING_ENABLED",
        "WORKER_HEARTBEAT_TTL_SECONDS",
        "DATABASE_URL",
        "REDIS_URL",
        "TIMEZONE",
        "LLM_PROVIDER",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OLLAMA_BASE_URL",
        "OLLAMA_API_KEY",
        "OLLAMA_MODEL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_OWNER_ID",
        "TELEGRAM_TARGET_CHANNEL_ID",
        "TELETHON_API_ID",
        "TELETHON_API_HASH",
        "TELETHON_SESSION_NAME",
        "REDDIT_CLIENT_ID",
        "REDDIT_CLIENT_SECRET",
        "REDDIT_USER_AGENT",
        "POSTIZ_BASE_URL",
        "POSTIZ_API_KEY",
        "POSTIZ_THREADS_INTEGRATION_ID",
        "POSTIZ_REDDIT_INTEGRATION_ID",
        "API_BASE_URL",
        "NEXT_PUBLIC_API_URL",
        "FRONTEND_ORIGIN",
        "PUBLIC_API_URL",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "COLLECT_INTERVAL_SECONDS",
        "GENERATE_INTERVAL_SECONDS",
        "PUBLISH_INTERVAL_SECONDS",
        "MASTER_ENCRYPTION_KEY",
        "MASTER_ENCRYPTION_KEYS_LEGACY",
        "ADMIN_TOKEN",
    ):
        if k not in ordered_keys and k in kv:
            ordered_keys.append(k)
    # Keep any unexpected vars at the end.
    for k in kv:
        if k not in ordered_keys:
            ordered_keys.append(k)
    lines = [f"{k}={kv[k]}" for k in ordered_keys]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    existing = _read_env(ENV_FILE)

    # Generate keys.
    master = _generate_master_key()
    admin = _generate_admin_token()

    # Build the new env. Start from current values, then apply desired flags,
    # then write keys. Never echo `master`.
    merged: dict[str, str] = {}
    # Defaults for every key the vault expects to see in .env.example.
    for k in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OLLAMA_BASE_URL",
        "OLLAMA_API_KEY",
        "OLLAMA_MODEL",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_OWNER_ID",
        "TELEGRAM_TARGET_CHANNEL_ID",
        "TELETHON_API_ID",
        "TELETHON_API_HASH",
        "REDDIT_CLIENT_ID",
        "REDDIT_CLIENT_SECRET",
        "POSTIZ_BASE_URL",
        "POSTIZ_API_KEY",
        "POSTIZ_THREADS_INTEGRATION_ID",
        "POSTIZ_REDDIT_INTEGRATION_ID",
        "FRONTEND_ORIGIN",
        "PUBLIC_API_URL",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "MASTER_ENCRYPTION_KEYS_LEGACY",
    ):
        merged[k] = ""
    merged["OLLAMA_MODEL"] = "kimi-k2.6:cloud"
    merged["TELETHON_SESSION_NAME"] = "chief_editor_session"
    merged["REDDIT_USER_AGENT"] = "ai-chief-editor-os-dev"
    merged["COLLECT_INTERVAL_SECONDS"] = "300"
    merged["GENERATE_INTERVAL_SECONDS"] = "600"
    merged["PUBLISH_INTERVAL_SECONDS"] = "30"

    # Existing values win over defaults.
    for k, v in existing.items():
        merged[k] = v

    # Live-mode flags overwrite anything else.
    for k, v in DESIRED_FLAGS.items():
        merged[k] = v

    # New secrets.
    merged["MASTER_ENCRYPTION_KEY"] = master
    merged["ADMIN_TOKEN"] = admin

    # Back up old .env once.
    backup = ENV_FILE.with_suffix(".env.bak")
    if ENV_FILE.exists() and not backup.exists():
        backup.write_text(
            ENV_FILE.read_text(encoding="utf-8"), encoding="utf-8"
        )

    _write_env(ENV_FILE, merged)

    # Print ONLY the admin token. Label it clearly.
    # The master key is in .env and never echoed.
    print("__ADMIN_TOKEN_FOR_UNLOCK__")
    print(admin)
    print("__END_ADMIN_TOKEN__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
