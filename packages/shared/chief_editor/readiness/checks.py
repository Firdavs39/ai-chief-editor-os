"""Per-integration readiness checks.

Two modes for each check:
- *passive* (no `live=True`): inspect env vars / DB only — never touches network.
- *active* (`live=True`): perform a single safe identity/read-only probe with a
  short timeout, and only if credentials are present.

Active probes must NEVER:
- send a message, comment, or post
- create or schedule any external resource
- log secret values

All exceptions are caught and downgraded to a `ReadinessItem` with
status=error and a safe truncated message.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
from sqlmodel import Session, select

from ..models import Source, WorkerHeartbeat
from ..services.integration_config import resolve_provider
from ..settings import Settings
from ..time_utils import to_utc, utcnow
from .models import ReadinessItem, ReadinessSeverity, ReadinessStatus, severity_for

log = logging.getLogger("chief_editor.readiness")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(
    key: str,
    label: str,
    status: ReadinessStatus,
    *,
    message: str = "",
    missing: list[str] | None = None,
    details: dict | None = None,
    can_test: bool = False,
    docs: str = "",
    next_action: str = "",
    severity: ReadinessSeverity | None = None,
) -> ReadinessItem:
    return ReadinessItem(
        key=key,
        label=label,
        status=status,
        severity=severity or severity_for(status),
        message=message,
        missing_env_vars=missing or [],
        safe_details=details or {},
        last_checked_at=utcnow(),
        can_test=can_test,
        docs_hint=docs,
        next_action=next_action,
    )


def _safe_error(key: str, label: str, exc: Exception, *, message: str = "") -> ReadinessItem:
    msg = (message or f"{type(exc).__name__}: {exc}")[:200]
    return _ok(key, label, ReadinessStatus.ERROR, message=msg, can_test=True)


def _key_meta(value: str) -> dict:
    """Safe metadata about a secret value — presence + length only.

    Never includes prefix/suffix or any substring of the value.
    """
    return {"present": bool(value), "length": len(value) if value else 0}


def _provider_sources(provider: str) -> dict[str, str]:
    """Per-field origin map for safe_details — {key_name: env|vault|missing}."""
    try:
        resolved = resolve_provider(provider)
    except KeyError:
        return {}
    return {name: rf.source for name, rf in resolved.items()}


def _aggregate_source(sources: dict[str, str]) -> str:
    """Combine per-field sources into a single label for the readiness row."""
    values = set(sources.values())
    if not values:
        return "missing"
    if values == {"missing"}:
        return "missing"
    if "env" in values:
        return "env" if values <= {"env", "missing"} else "env+vault"
    if "vault" in values:
        return "vault"
    return "missing"


# ---------------------------------------------------------------------------
# Mode flags
# ---------------------------------------------------------------------------


def check_mode(s: Settings) -> list[ReadinessItem]:
    items = []

    items.append(
        _ok(
            "mode.demo",
            "Demo Mode",
            ReadinessStatus.VALID if s.demo_mode else ReadinessStatus.DISABLED,
            message=(
                "Demo seed and fallback data drive the dashboard."
                if s.demo_mode
                else "Live data only — no fallback."
            ),
            details={"enabled": s.demo_mode},
            severity=ReadinessSeverity.INFO,
        )
    )

    items.append(
        _ok(
            "mode.mock",
            "Mock Mode (adapters)",
            ReadinessStatus.VALID if s.mock_mode else ReadinessStatus.DISABLED,
            message=(
                "External adapters degrade to mock when credentials are missing."
                if s.mock_mode
                else "Real adapters required — missing credentials will surface as errors."
            ),
            details={"enabled": s.mock_mode},
            severity=ReadinessSeverity.INFO,
        )
    )

    items.append(
        _ok(
            "mode.live",
            "Live Mode",
            ReadinessStatus.VALID if s.live_mode else ReadinessStatus.DISABLED,
            message=(
                "UI expects real configuration; missing pieces appear as warnings."
                if s.live_mode
                else "Demo mode UX. Missing credentials are silent."
            ),
            details={"enabled": s.live_mode},
            severity=ReadinessSeverity.INFO,
        )
    )

    items.append(
        _ok(
            "mode.dry_run",
            "Dry Run Publishing",
            ReadinessStatus.VALID if s.dry_run_publish else ReadinessStatus.DISABLED,
            message=(
                "Publisher computes payload but does NOT contact external services."
                if s.dry_run_publish
                else "Real publishing path is active."
            ),
            details={"enabled": s.dry_run_publish},
            severity=ReadinessSeverity.INFO if s.dry_run_publish else ReadinessSeverity.WARNING,
        )
    )

    items.append(
        _ok(
            "mode.publishing_enabled",
            "Publishing Enabled",
            ReadinessStatus.VALID if s.publishing_enabled else ReadinessStatus.DISABLED,
            message=(
                "Master gate is ON. Approved jobs may be dispatched."
                if s.publishing_enabled
                else "Master gate is OFF — no real publish path can run."
            ),
            details={"enabled": s.publishing_enabled},
            severity=(
                ReadinessSeverity.WARNING
                if s.publishing_enabled
                else ReadinessSeverity.INFO
            ),
            next_action=(
                "Set PUBLISHING_ENABLED=true in .env once Live Mode is validated."
                if not s.publishing_enabled
                else "Keep DRY_RUN_PUBLISH=true until first real test is confirmed."
            ),
        )
    )

    return items


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------


def check_llm(s: Settings, *, live: bool = False) -> ReadinessItem:
    key = "llm.provider"
    label = f"LLM provider — {s.llm_provider}"
    docs = "docs/INTEGRATIONS.md#llm"

    if s.mock_mode or s.llm_provider == "mock":
        return _ok(
            key,
            "LLM — mock provider",
            ReadinessStatus.MOCK,
            message="Deterministic mock LLM in use. Safe for demo and tests.",
            details={"provider": "mock"},
            can_test=True,
            docs=docs,
        )

    if s.llm_provider == "anthropic":
        sources = _provider_sources("anthropic")
        resolved = resolve_provider("anthropic")
        api_key = resolved["api_key"].value or ""
        model_override = resolved["model"].value or ""
        if not api_key:
            return _ok(
                key,
                label,
                ReadinessStatus.MISSING_CONFIG,
                message="Anthropic API key is not set (env or vault).",
                missing=["ANTHROPIC_API_KEY"],
                details={"provider": "anthropic", "sources": sources, "source": _aggregate_source(sources)},
                can_test=True,
                docs=docs,
                next_action="Add ANTHROPIC_API_KEY to .env or save it in Settings → Integrations vault.",
            )
        if not live:
            return _ok(
                key,
                label,
                ReadinessStatus.CONFIGURED,
                message=f"Anthropic key present (source: {sources['api_key']}) — click Test to verify.",
                details={
                    "provider": "anthropic",
                    "key": _key_meta(api_key),
                    "sources": sources,
                    "source": _aggregate_source(sources),
                },
                can_test=True,
                docs=docs,
            )
        try:
            from ..llm.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider(api_key, model_override or s.anthropic_model)
            result = provider.complete_json(
                system="You are a JSON-only readiness probe.",
                user='Reply with exactly {"ok": true}.',
                schema={
                    "type": "object",
                    "required": ["ok"],
                    "properties": {"ok": {"type": "boolean"}},
                },
                temperature=0,
            )
            ok = bool(result.get("ok"))
            return _ok(
                key,
                label,
                ReadinessStatus.VALID if ok else ReadinessStatus.INVALID,
                message="Anthropic responded with valid structured JSON." if ok else "Anthropic responded but JSON shape is unexpected.",
                details={
                    "provider": "anthropic",
                    "model": model_override or s.anthropic_model,
                    "sources": sources,
                    "source": _aggregate_source(sources),
                },
                can_test=True,
                docs=docs,
            )
        except Exception as exc:  # noqa: BLE001
            return _safe_error(key, label, exc, message=f"Anthropic probe failed: {type(exc).__name__}")

    if s.llm_provider == "openai":
        sources = _provider_sources("openai")
        resolved = resolve_provider("openai")
        api_key = resolved["api_key"].value or ""
        model_override = resolved["model"].value or ""
        if not api_key:
            return _ok(
                key,
                label,
                ReadinessStatus.MISSING_CONFIG,
                message="OpenAI API key is not set (env or vault).",
                missing=["OPENAI_API_KEY"],
                details={"provider": "openai", "sources": sources, "source": _aggregate_source(sources)},
                can_test=True,
                docs=docs,
                next_action="Add OPENAI_API_KEY to .env or save it in Settings → Integrations vault.",
            )
        if not live:
            return _ok(
                key,
                label,
                ReadinessStatus.CONFIGURED,
                message=f"OpenAI key present (source: {sources['api_key']}) — click Test to verify.",
                details={
                    "provider": "openai",
                    "key": _key_meta(api_key),
                    "sources": sources,
                    "source": _aggregate_source(sources),
                },
                can_test=True,
                docs=docs,
            )
        try:
            from ..llm.openai_provider import OpenAIProvider

            provider = OpenAIProvider(api_key, model_override or s.openai_model)
            result = provider.complete_json(
                system="You are a JSON-only readiness probe.",
                user='Reply with exactly {"ok": true}.',
                schema={
                    "type": "object",
                    "required": ["ok"],
                    "properties": {"ok": {"type": "boolean"}},
                },
                temperature=0,
            )
            ok = bool(result.get("ok"))
            return _ok(
                key,
                label,
                ReadinessStatus.VALID if ok else ReadinessStatus.INVALID,
                message="OpenAI responded with valid structured JSON." if ok else "OpenAI JSON shape unexpected.",
                details={
                    "provider": "openai",
                    "model": model_override or s.openai_model,
                    "sources": sources,
                    "source": _aggregate_source(sources),
                },
                can_test=True,
                docs=docs,
            )
        except Exception as exc:  # noqa: BLE001
            return _safe_error(key, label, exc, message=f"OpenAI probe failed: {type(exc).__name__}")

    if s.llm_provider == "ollama":
        from ..llm.ollama_provider import host_of

        sources = _provider_sources("ollama")
        resolved = resolve_provider("ollama")
        base_url = resolved["base_url"].value or ""
        api_key_value = resolved["api_key"].value or ""
        model_value = resolved["model"].value or s.ollama_model

        is_local = bool(base_url and any(
            host in base_url.lower()
            for host in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal")
        ))

        missing: list[str] = []
        if not base_url:
            missing.append("OLLAMA_BASE_URL")
        if not is_local and not api_key_value:
            missing.append("OLLAMA_API_KEY")
        if missing:
            return _ok(
                key,
                "LLM — Ollama / Kimi K2.6",
                ReadinessStatus.MISSING_CONFIG,
                message=(
                    "Ollama requires a base URL (and an API key for remote endpoints)."
                ),
                missing=missing,
                details={
                    "provider": "ollama",
                    "model": model_value,
                    "sources": sources,
                    "source": _aggregate_source(sources),
                },
                can_test=True,
                docs=docs,
                next_action=(
                    "Set OLLAMA_BASE_URL=https://ollama.com and OLLAMA_API_KEY, "
                    "or run a local Ollama at http://localhost:11434. "
                    "You can also save these in Settings → Integrations vault."
                ),
            )

        safe_details = {
            "provider": "ollama",
            "model": model_value,
            "base_url_host": host_of(base_url),
            "is_local": is_local,
            "api_key": _key_meta(api_key_value) if api_key_value else {
                "present": False,
                "length": 0,
            },
            "sources": sources,
            "source": _aggregate_source(sources),
        }
        effective_key = api_key_value or ("ollama" if is_local else "")

        if not live:
            return _ok(
                key,
                "LLM — Ollama / Kimi K2.6",
                ReadinessStatus.CONFIGURED,
                message="Ollama configured — click Test to verify the model responds with valid JSON.",
                details=safe_details,
                can_test=True,
                docs=docs,
                next_action=(
                    "Ollama must be reachable from the API runtime; if the backend "
                    "is on Vercel/Fly and Ollama is local, expose it via a tunnel."
                ),
            )

        try:
            from ..llm.ollama_provider import OllamaProvider

            provider = OllamaProvider(
                base_url=base_url,
                api_key=effective_key,
                model=model_value,
            )
            result = provider.complete_json(
                system="You are a JSON-only readiness probe.",
                user='Reply with exactly {"ok": true, "provider": "ollama"}.',
                schema={
                    "type": "object",
                    "required": ["ok"],
                    "properties": {
                        "ok": {"type": "boolean"},
                        "provider": {"type": "string"},
                    },
                },
                temperature=0,
            )
            ok = bool(result.get("ok"))
            return _ok(
                key,
                "LLM — Ollama / Kimi K2.6",
                ReadinessStatus.VALID if ok else ReadinessStatus.INVALID,
                message=(
                    f"Ollama returned valid JSON via {model_value}."
                    if ok
                    else "Ollama responded but JSON shape unexpected."
                ),
                details=safe_details,
                can_test=True,
                docs=docs,
            )
        except Exception as exc:  # noqa: BLE001
            return _safe_error(
                key,
                "LLM — Ollama / Kimi K2.6",
                exc,
                message=f"Ollama probe failed: {type(exc).__name__}",
            )

    return _ok(
        key,
        label,
        ReadinessStatus.UNAVAILABLE,
        message=f"Unknown provider: {s.llm_provider}",
        can_test=False,
        docs=docs,
    )


# ---------------------------------------------------------------------------
# Telegram (Bot API)
# ---------------------------------------------------------------------------


def check_telegram_bot(s: Settings, *, live: bool = False) -> ReadinessItem:
    key = "telegram.bot"
    label = "Telegram — publish bot"
    docs = "docs/INTEGRATIONS.md#telegram-publish"

    sources = _provider_sources("telegram_bot")
    resolved = resolve_provider("telegram_bot")
    token = resolved["bot_token"].value or ""
    target = resolved["target_channel_id"].value or ""

    if not token:
        return _ok(
            key,
            label,
            ReadinessStatus.MISSING_CONFIG,
            message="TELEGRAM_BOT_TOKEN is not set (env or vault).",
            missing=(
                ["TELEGRAM_BOT_TOKEN", "TELEGRAM_TARGET_CHANNEL_ID"]
                if not target
                else ["TELEGRAM_BOT_TOKEN"]
            ),
            details={"sources": sources, "source": _aggregate_source(sources)},
            can_test=True,
            docs=docs,
            next_action=(
                "Create a bot via @BotFather and paste the token, or save it in "
                "Settings → Integrations vault."
            ),
        )

    details: dict = {
        "token": _key_meta(token),
        "target_channel_present": bool(target),
        "sources": sources,
        "source": _aggregate_source(sources),
    }

    if not live:
        return _ok(
            key,
            label,
            ReadinessStatus.CONFIGURED,
            message=f"Token present (source: {sources['bot_token']}) — click Test to call getMe.",
            details=details,
            can_test=True,
            docs=docs,
        )

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"https://api.telegram.org/bot{token}/getMe")
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            bot = data.get("result", {})
            details.update(
                {
                    "bot_id": bot.get("id"),
                    "bot_username": bot.get("username"),
                    "can_join_groups": bot.get("can_join_groups"),
                }
            )
            return _ok(
                key,
                label,
                ReadinessStatus.VALID,
                message=f"Bot @{bot.get('username','?')} responded to getMe.",
                details=details,
                can_test=True,
                docs=docs,
            )
        return _ok(
            key,
            label,
            ReadinessStatus.INVALID,
            message=f"Telegram rejected token (HTTP {resp.status_code}).",
            details=details,
            can_test=True,
            docs=docs,
        )
    except Exception as exc:  # noqa: BLE001
        return _safe_error(key, label, exc, message=f"Telegram getMe failed: {type(exc).__name__}")


# ---------------------------------------------------------------------------
# Telethon (client-style monitoring)
# ---------------------------------------------------------------------------


def check_telethon(s: Settings, *, live: bool = False) -> ReadinessItem:
    key = "telethon.session"
    label = "Telegram — Telethon monitor"
    docs = "docs/INTEGRATIONS.md#telethon"

    sources = _provider_sources("telethon")
    resolved = resolve_provider("telethon")
    api_id = resolved["api_id"].value or ""
    api_hash = resolved["api_hash"].value or ""

    if not (api_id and api_hash):
        return _ok(
            key,
            label,
            ReadinessStatus.MISSING_CONFIG,
            message="TELETHON_API_ID and TELETHON_API_HASH must both be set (env or vault).",
            missing=["TELETHON_API_ID", "TELETHON_API_HASH"],
            details={"sources": sources, "source": _aggregate_source(sources)},
            can_test=True,
            docs=docs,
            next_action=(
                "Register an app at https://my.telegram.org and paste api_id / api_hash. "
                "You can also save them in Settings → Integrations vault."
            ),
        )

    session_path = Path(f"{s.telethon_session_name}.session")
    has_session = session_path.exists() and session_path.is_file()

    details = {
        "api_id_present": bool(api_id),
        "api_hash": _key_meta(api_hash),
        "session_name": s.telethon_session_name,
        "session_file_exists": has_session,
        "needs_session": not has_session,
        "sources": sources,
        "source": _aggregate_source(sources),
    }

    if not has_session:
        return _ok(
            key,
            label,
            ReadinessStatus.CONFIGURED,
            message="Credentials present but no Telethon session file. Interactive login is required (CLI only).",
            details=details,
            can_test=True,
            docs=docs,
            next_action="Run the CLI runbook to create a session — see docs/INTEGRATIONS.md#telethon.",
        )

    # We never attempt to log in from a web request — that requires interactive
    # 2FA input. The presence of a session file is the best we can verify here.
    return _ok(
        key,
        label,
        ReadinessStatus.VALID,
        message="Credentials and session file present. Ready for monitoring loops.",
        details=details,
        can_test=True,
        docs=docs,
    )


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------


def check_reddit(s: Settings, *, live: bool = False) -> ReadinessItem:
    key = "reddit.api"
    label = "Reddit — official API"
    docs = "docs/INTEGRATIONS.md#reddit"

    sources = _provider_sources("reddit")
    resolved = resolve_provider("reddit")
    client_id = resolved["client_id"].value or ""
    client_secret = resolved["client_secret"].value or ""
    user_agent = resolved["user_agent"].value or s.reddit_user_agent

    if not (client_id and client_secret):
        return _ok(
            key,
            label,
            ReadinessStatus.MISSING_CONFIG,
            message="REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must both be set (env or vault).",
            missing=["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"],
            details={"sources": sources, "source": _aggregate_source(sources)},
            can_test=True,
            docs=docs,
            next_action=(
                "Register a script app at https://reddit.com/prefs/apps, or save the credentials "
                "in Settings → Integrations vault."
            ),
        )

    if not user_agent or user_agent.startswith("ai-chief-editor-os"):
        ua_note = "Default user-agent is fine for dev, but production should identify your app."
    else:
        ua_note = "Custom user-agent set."

    details = {
        "client_id": _key_meta(client_id),
        "client_secret": _key_meta(client_secret),
        "user_agent": user_agent,
        "user_agent_note": ua_note,
        "sources": sources,
        "source": _aggregate_source(sources),
    }

    if not live:
        return _ok(
            key,
            label,
            ReadinessStatus.CONFIGURED,
            message="Credentials present — click Test to verify OAuth.",
            details=details,
            can_test=True,
            docs=docs,
        )

    # Live test — OAuth client_credentials grant against Reddit.
    try:
        auth = httpx.BasicAuth(client_id, client_secret)
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": user_agent},
                auth=auth,
            )
        if resp.status_code == 200 and resp.json().get("access_token"):
            return _ok(
                key,
                label,
                ReadinessStatus.VALID,
                message="Reddit issued an access token. Read-only API ready.",
                details=details,
                can_test=True,
                docs=docs,
            )
        return _ok(
            key,
            label,
            ReadinessStatus.INVALID,
            message=f"Reddit rejected credentials (HTTP {resp.status_code}).",
            details=details,
            can_test=True,
            docs=docs,
        )
    except Exception as exc:  # noqa: BLE001
        return _safe_error(key, label, exc, message=f"Reddit probe failed: {type(exc).__name__}")


# ---------------------------------------------------------------------------
# Postiz
# ---------------------------------------------------------------------------


def check_postiz(s: Settings, *, live: bool = False) -> ReadinessItem:
    key = "postiz.api"
    label = "Postiz — Threads + Reddit publish"
    docs = "docs/INTEGRATIONS.md#postiz"

    sources = _provider_sources("postiz")
    resolved = resolve_provider("postiz")
    base_url = resolved["base_url"].value or ""
    api_key = resolved["api_key"].value or ""
    threads_id = resolved["threads_integration_id"].value or ""
    reddit_id = resolved["reddit_integration_id"].value or ""

    missing: list[str] = []
    if not base_url:
        missing.append("POSTIZ_BASE_URL")
    if not api_key:
        missing.append("POSTIZ_API_KEY")
    if missing:
        return _ok(
            key,
            label,
            ReadinessStatus.MISSING_CONFIG,
            message="Postiz base URL and API key are required (env or vault).",
            missing=missing,
            details={"sources": sources, "source": _aggregate_source(sources)},
            can_test=True,
            docs=docs,
            next_action=(
                "Configure Postiz at https://postiz.com and copy base URL + API key, "
                "or save them in Settings → Integrations vault."
            ),
        )

    details = {
        "base_url": base_url,
        "api_key": _key_meta(api_key),
        "threads_integration_id_present": bool(threads_id),
        "reddit_integration_id_present": bool(reddit_id),
        "sources": sources,
        "source": _aggregate_source(sources),
    }
    integrations_note = []
    if not threads_id:
        integrations_note.append("Threads publishing unavailable until POSTIZ_THREADS_INTEGRATION_ID is set.")
    if not reddit_id:
        integrations_note.append("Reddit via Postiz unavailable until POSTIZ_REDDIT_INTEGRATION_ID is set.")

    if not live:
        return _ok(
            key,
            label,
            ReadinessStatus.CONFIGURED,
            message="Credentials present — click Test to call Postiz read endpoint.",
            details=details,
            can_test=True,
            docs=docs,
            next_action="; ".join(integrations_note) if integrations_note else "",
        )

    # Live probe — call a SAFE read endpoint. Try `/api/integrations` first
    # (per Postiz docs), fall back to `/api/posts?limit=1`. Both are read-only.
    base = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    last_status: int | None = None
    last_err: str | None = None
    for path in ("/api/v1/integrations", "/api/integrations", "/api/posts?limit=1"):
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{base}{path}", headers=headers)
            last_status = resp.status_code
            if resp.status_code < 400:
                details["probe_path"] = path
                details["probe_status"] = resp.status_code
                return _ok(
                    key,
                    label,
                    ReadinessStatus.VALID,
                    message=f"Postiz responded {resp.status_code} on {path}.",
                    details=details,
                    can_test=True,
                    docs=docs,
                    next_action="; ".join(integrations_note) if integrations_note else "",
                )
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"[:120]
            continue
    return _ok(
        key,
        label,
        ReadinessStatus.INVALID,
        message=f"Postiz did not respond to read probes. Last status={last_status}; err={last_err}",
        details=details,
        can_test=True,
        docs=docs,
    )


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------


def check_vault(s: Settings) -> ReadinessItem:
    """Surface whether the Integration Secrets Vault is enabled.

    Reports only that MASTER_ENCRYPTION_KEY is present — no key material.
    """
    from ..services.secrets import is_vault_enabled

    enabled = is_vault_enabled()
    legacy = len(s.legacy_encryption_keys)
    return _ok(
        "vault.encryption",
        "Secrets vault — encryption",
        ReadinessStatus.VALID if enabled else ReadinessStatus.DISABLED,
        message=(
            "Encrypted credential vault is active. Saved secrets are stored "
            "with Fernet (AES-128-CBC + HMAC-SHA256)."
            if enabled
            else "Vault is disabled — MASTER_ENCRYPTION_KEY is not set. "
            "Env-based credentials still work."
        ),
        details={
            "enabled": enabled,
            "legacy_keys_configured": legacy,
            "admin_token_set": bool(s.admin_token),
        },
        missing=["MASTER_ENCRYPTION_KEY"] if not enabled else [],
        severity=ReadinessSeverity.SUCCESS if enabled else ReadinessSeverity.INFO,
        docs="docs/SECRETS_VAULT.md",
        next_action=(
            "Generate with: python -m chief_editor.services.secrets generate-key"
            if not enabled
            else ""
        ),
    )


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


def check_worker(session: Session, s: Settings) -> ReadinessItem:
    key = "worker.heartbeat"
    label = "Worker process"
    ttl = max(15, s.worker_heartbeat_ttl_seconds)

    rows = list(session.exec(select(WorkerHeartbeat)).all())
    if not rows:
        return _ok(
            key,
            label,
            ReadinessStatus.UNAVAILABLE,
            message="No worker heartbeat recorded yet. Worker may not be running.",
            details={"ttl_seconds": ttl, "loops": {}},
            can_test=False,
            next_action="Start the worker: `python -m worker.main` or `docker compose up worker`.",
        )

    now = utcnow()
    loops: dict[str, dict] = {}
    fresh = True
    for row in rows:
        last_at = to_utc(row.last_at) if row.last_at else None
        age = (now - last_at).total_seconds() if last_at else 1e9
        is_fresh = age <= ttl
        if not is_fresh:
            fresh = False
        loops[row.loop_name] = {
            "last_at": last_at.isoformat() if last_at else None,
            "last_event": row.last_event,
            "age_seconds": int(age),
            "fresh": is_fresh,
            "counter": row.counter,
        }

    return _ok(
        key,
        label,
        ReadinessStatus.VALID if fresh else ReadinessStatus.UNAVAILABLE,
        message=(
            f"All {len(loops)} worker loops fresh (within {ttl}s)."
            if fresh
            else "One or more worker loops have stale heartbeats."
        ),
        details={"ttl_seconds": ttl, "loops": loops},
        can_test=False,
    )


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


def check_sources(session: Session, s: Settings) -> list[ReadinessItem]:
    sources = list(session.exec(select(Source)).all())
    if not sources:
        return [
            _ok(
                "sources.empty",
                "Sources",
                ReadinessStatus.UNAVAILABLE,
                message="No sources registered. Add at least one via /sources.",
                next_action="POST /sources or use the demo seed.",
            )
        ]

    items: list[ReadinessItem] = []
    by_kind: dict[str, list[Source]] = {}
    for src in sources:
        by_kind.setdefault(src.kind, []).append(src)

    for kind, group in by_kind.items():
        enabled = sum(1 for x in group if x.enabled)
        healthy = sum(1 for x in group if (x.health or {}).get("ok", True))

        if kind == "telegram":
            telethon_resolved = resolve_provider("telethon")
            telethon_ready = bool(
                (telethon_resolved["api_id"].value)
                and (telethon_resolved["api_hash"].value)
            )
            ready = telethon_ready or s.mock_mode
            status = (
                ReadinessStatus.MOCK
                if s.mock_mode and not telethon_ready
                else ReadinessStatus.VALID
                if ready
                else ReadinessStatus.MISSING_CONFIG
            )
            missing = [] if ready else ["TELETHON_API_ID", "TELETHON_API_HASH"]
            message = f"{enabled}/{len(group)} Telegram sources enabled. {'Live ready.' if telethon_ready else 'Mock-only.'}"
        elif kind == "reddit":
            reddit_resolved = resolve_provider("reddit")
            reddit_ready = bool(
                (reddit_resolved["client_id"].value)
                and (reddit_resolved["client_secret"].value)
            )
            ready = reddit_ready or s.mock_mode
            status = (
                ReadinessStatus.MOCK
                if s.mock_mode and not reddit_ready
                else ReadinessStatus.VALID
                if ready
                else ReadinessStatus.MISSING_CONFIG
            )
            missing = [] if ready else ["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]
            message = f"{enabled}/{len(group)} Reddit sources enabled. {'Live ready.' if reddit_ready else 'Mock-only.'}"
        elif kind == "rss":
            status = ReadinessStatus.VALID
            missing = []
            message = f"{enabled}/{len(group)} RSS feeds enabled. No credentials needed."
        else:
            status = ReadinessStatus.MOCK
            missing = []
            message = f"{enabled}/{len(group)} {kind} sources."

        items.append(
            _ok(
                f"sources.{kind}",
                f"Sources — {kind}",
                status,
                message=message,
                missing=missing,
                details={
                    "total": len(group),
                    "enabled": enabled,
                    "healthy": healthy,
                },
                can_test=False,
            )
        )

    return items


# ---------------------------------------------------------------------------
# Publishing safety
# ---------------------------------------------------------------------------


def check_publishing_safety(s: Settings) -> list[ReadinessItem]:
    items: list[ReadinessItem] = []

    items.append(
        _ok(
            "safety.approval_gate",
            "Approval gate (mandatory)",
            ReadinessStatus.VALID,
            message="Three-layer enforcement: API route, worker dispatch, publisher boundary.",
            severity=ReadinessSeverity.SUCCESS,
        )
    )

    if not s.publishing_enabled:
        items.append(
            _ok(
                "safety.master_switch",
                "Master switch — PUBLISHING_ENABLED",
                ReadinessStatus.DISABLED,
                message="No real publish path is reachable. Approve → blocked.",
                severity=ReadinessSeverity.INFO,
                details={"enabled": False},
                next_action="Keep this OFF until DRY_RUN_PUBLISH preview is reviewed.",
            )
        )
    else:
        items.append(
            _ok(
                "safety.master_switch",
                "Master switch — PUBLISHING_ENABLED",
                ReadinessStatus.VALID,
                message="Master gate is ON. Real publishing path is reachable for approved jobs.",
                severity=ReadinessSeverity.WARNING,
                details={"enabled": True},
            )
        )

    if s.dry_run_publish:
        items.append(
            _ok(
                "safety.dry_run",
                "Dry-run publishing",
                ReadinessStatus.VALID,
                message="Publisher will compute payload but not contact external services.",
                severity=ReadinessSeverity.INFO,
                details={"enabled": True},
            )
        )
    else:
        items.append(
            _ok(
                "safety.dry_run",
                "Dry-run publishing",
                ReadinessStatus.DISABLED,
                message="Dry-run is OFF — approved jobs may be sent for real (if master switch is ON).",
                severity=ReadinessSeverity.WARNING,
                details={"enabled": False},
            )
        )

    if s.mock_mode:
        items.append(
            _ok(
                "safety.mock_mode",
                "Adapter fallback (MOCK_MODE)",
                ReadinessStatus.VALID,
                message="Missing credentials degrade to mock — no silent failures.",
                severity=ReadinessSeverity.INFO,
                details={"enabled": True},
            )
        )

    return items


# ---------------------------------------------------------------------------
# Source (per-source) test
# ---------------------------------------------------------------------------


def test_source(session: Session, source: Source, s: Settings) -> ReadinessItem:
    key = f"source.{source.id}"
    label = f"{source.kind}:{source.handle}"
    if not source.enabled:
        return _ok(
            key,
            label,
            ReadinessStatus.DISABLED,
            message="Source is disabled.",
        )

    if source.kind == "rss":
        if not source.url:
            return _ok(
                key,
                label,
                ReadinessStatus.MISSING_CONFIG,
                message="RSS source requires a URL.",
            )
        try:
            with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                resp = client.get(source.url, headers={"User-Agent": "chief-editor-readiness/0.1"})
            if resp.status_code < 400 and ("xml" in resp.headers.get("content-type", "").lower() or resp.text.lstrip().startswith("<?xml")):
                return _ok(
                    key,
                    label,
                    ReadinessStatus.VALID,
                    message=f"Feed reachable ({resp.status_code}, {len(resp.text)} bytes).",
                    details={"url": source.url, "status": resp.status_code},
                )
            return _ok(
                key,
                label,
                ReadinessStatus.INVALID,
                message=f"Feed responded {resp.status_code} but no XML content detected.",
                details={"url": source.url, "status": resp.status_code},
            )
        except Exception as exc:  # noqa: BLE001
            return _safe_error(key, label, exc)

    if source.kind == "telegram":
        telethon_resolved = resolve_provider("telethon")
        if not (telethon_resolved["api_id"].value and telethon_resolved["api_hash"].value):
            return _ok(
                key,
                label,
                ReadinessStatus.MISSING_CONFIG,
                message="TELETHON credentials required for Telegram monitoring.",
                missing=["TELETHON_API_ID", "TELETHON_API_HASH"],
            )
        return _ok(
            key,
            label,
            ReadinessStatus.CONFIGURED,
            message="Telethon credentials present. Per-source live ping requires session file.",
        )

    if source.kind == "reddit":
        reddit_resolved = resolve_provider("reddit")
        if not (reddit_resolved["client_id"].value and reddit_resolved["client_secret"].value):
            return _ok(
                key,
                label,
                ReadinessStatus.MISSING_CONFIG,
                message="Reddit credentials required.",
                missing=["REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"],
            )
        return _ok(
            key,
            label,
            ReadinessStatus.CONFIGURED,
            message="Reddit credentials present. Full read test available via /readiness/test-reddit.",
        )

    return _ok(
        key,
        label,
        ReadinessStatus.MOCK,
        message=f"{source.kind} source has no live probe — runs as mock.",
    )


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------


def compute_score(sections: list) -> tuple[int, str]:
    items = [it for sec in sections for it in sec.items]
    if not items:
        return 0, "demo"
    good = sum(
        1
        for it in items
        if it.status
        in {
            ReadinessStatus.VALID,
            ReadinessStatus.MOCK,
            ReadinessStatus.CONFIGURED,
        }
    )
    score = int(round(good * 100 / len(items)))
    if score >= 90:
        label = "ready"
    elif score >= 70:
        label = "close"
    elif score >= 50:
        label = "partial"
    else:
        label = "demo"
    return score, label
