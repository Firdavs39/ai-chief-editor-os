"""Integration Secrets Vault router.

All endpoints are gated by `require_admin_token`. None of them publish.
GET endpoints return safe metadata only — never plaintext, never tokens.
POST/DELETE accept secret values but reflect back only safe metadata.

When MASTER_ENCRYPTION_KEY is unset the vault is disabled: write/test/get
endpoints return HTTP 409. Existing env-based credentials keep working.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from chief_editor.llm import registry as llm_registry
from chief_editor.models import IntegrationSecret, SystemLog
from chief_editor.readiness.models import (
    ReadinessItem,
    ReadinessSeverity,
    ReadinessStatus,
)
from chief_editor.services.integration_config import resolve_provider
from chief_editor.services.secrets import (
    SUPPORTED_PROVIDERS,
    KeyRotationError,
    VaultDisabledError,
    encrypt,
    get_provider_spec,
    is_vault_enabled,
    safe_metadata_for,
)
from chief_editor.settings import get_settings
from chief_editor.time_utils import utcnow

from ..deps import get_session, require_admin_token

log = logging.getLogger("chief_editor.secrets")

router = APIRouter(
    prefix="/secrets",
    tags=["secrets"],
    dependencies=[Depends(require_admin_token)],
)


# ---------------------------------------------------------------------------
# Pydantic response models — never carry plaintext or encrypted tokens.
# ---------------------------------------------------------------------------


class FieldStatus(BaseModel):
    key_name: str
    label: str
    is_secret: bool
    required: bool
    env_var: str
    placeholder: str
    source: Literal["env", "vault", "missing"]
    advanced: bool = False
    safe_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderSummary(BaseModel):
    provider: str
    label: str
    docs_anchor: str
    status: str = "unknown"
    last_tested_at: datetime | None = None
    last_test_message: str = ""
    fields: list[FieldStatus] = Field(default_factory=list)
    can_test: bool = True
    source: Literal["env", "vault", "missing", "env+vault"] = "missing"


class VaultListResponse(BaseModel):
    vault_enabled: bool
    admin_token_required: bool
    providers: list[ProviderSummary]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _audit(session: Session, event: str, **data: Any) -> None:
    """Write a vault audit log. Caller is responsible for keeping `data` safe.

    SystemLog.data bypasses the structlog redactor — so this helper accepts
    only known-safe keys. Callers must NEVER pass plaintext secrets.
    """
    safe_keys = {
        "provider",
        "key_name",
        "length",
        "is_secret",
        "source",
        "status",
        "reason",
        "fields_written",
        "fields_deleted",
        "rows_deleted",
        "host",
        "client_host",
    }
    cleaned = {k: v for k, v in data.items() if k in safe_keys}
    session.add(SystemLog(level="info", event=event, message="", data=cleaned))
    session.commit()


def _provider_or_404(provider: str) -> Any:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=404, detail="unknown_provider")
    return get_provider_spec(provider)


def _vault_enabled_or_409() -> None:
    if not is_vault_enabled():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "status": "disabled",
                "reason": "missing_master_key",
                "message": (
                    "Set MASTER_ENCRYPTION_KEY to enable the vault. "
                    "Existing env-based credentials keep working."
                ),
            },
        )


def _row(session: Session, provider: str, key_name: str) -> IntegrationSecret | None:
    return session.exec(
        select(IntegrationSecret).where(
            IntegrationSecret.provider == provider,
            IntegrationSecret.key_name == key_name,
        )
    ).first()


def _rows_for(session: Session, provider: str) -> list[IntegrationSecret]:
    return list(
        session.exec(
            select(IntegrationSecret).where(IntegrationSecret.provider == provider)
        ).all()
    )


def _aggregate(field_sources: list[str]) -> Literal["env", "vault", "missing", "env+vault"]:
    s = set(field_sources)
    if not s or s == {"missing"}:
        return "missing"
    if "env" in s and "vault" in s:
        return "env+vault"
    if "env" in s:
        return "env"
    return "vault"


def _build_summary(session: Session, provider: str) -> ProviderSummary:
    spec = get_provider_spec(provider)
    resolved = resolve_provider(provider, session=session)
    rows = {row.key_name: row for row in _rows_for(session, provider)}

    fields: list[FieldStatus] = []
    for field in spec.fields:
        rf = resolved[field.key_name]
        row = rows.get(field.key_name)
        meta: dict[str, Any]
        if rf.source == "env":
            meta = {"is_secret": field.is_secret, "source": "env"}
            if field.is_secret:
                meta["length"] = len(rf.value or "")
            else:
                meta["value"] = rf.value or ""
        elif rf.source == "vault":
            meta = dict(row.safe_metadata) if row and row.safe_metadata else {}
            meta.setdefault("is_secret", field.is_secret)
        else:
            meta = {"is_secret": field.is_secret, "length": 0}

        fields.append(
            FieldStatus(
                key_name=field.key_name,
                label=field.label,
                is_secret=field.is_secret,
                required=field.required,
                env_var=field.env_var,
                placeholder=field.placeholder,
                source=rf.source,
                advanced=field.advanced,
                safe_metadata=meta,
            )
        )

    # Aggregate provider-level status from rows (any row that has been tested
    # contributes a status; we prefer "valid" > "invalid"/"error" > "configured").
    status_priority = {
        "valid": 4,
        "invalid": 3,
        "error": 3,
        "configured": 2,
        "unknown": 1,
    }
    chosen_status = "unknown"
    last_tested: datetime | None = None
    last_msg = ""
    for row in rows.values():
        if row.last_tested_at and (last_tested is None or row.last_tested_at > last_tested):
            last_tested = row.last_tested_at
            last_msg = row.last_test_message
        if status_priority.get(row.status, 0) > status_priority.get(chosen_status, 0):
            chosen_status = row.status

    # If no row but env-configured, surface as "configured".
    if chosen_status == "unknown" and any(f.source == "env" for f in fields):
        chosen_status = "configured"

    return ProviderSummary(
        provider=provider,
        label=spec.label,
        docs_anchor=spec.docs_anchor,
        status=chosen_status,
        last_tested_at=last_tested,
        last_test_message=last_msg,
        fields=fields,
        can_test=True,
        source=_aggregate([f.source for f in fields]),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/integrations", response_model=VaultListResponse)
def list_integrations(session: Session = Depends(get_session)) -> VaultListResponse:
    """Per-provider summary for all supported integrations."""
    s = get_settings()
    providers = [_build_summary(session, p) for p in SUPPORTED_PROVIDERS]
    return VaultListResponse(
        vault_enabled=is_vault_enabled(),
        admin_token_required=bool((s.admin_token or "").strip()),
        providers=providers,
    )


@router.get("/{provider}", response_model=ProviderSummary)
def get_provider(provider: str, session: Session = Depends(get_session)) -> ProviderSummary:
    _provider_or_404(provider)
    return _build_summary(session, provider)


class SecretPayload(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)


@router.post("/{provider}", response_model=ProviderSummary)
def upsert_provider_secrets(
    provider: str,
    payload: SecretPayload,
    session: Session = Depends(get_session),
) -> ProviderSummary:
    """Save (or delete-on-empty) values for the given provider.

    Body: {"values": {"<key_name>": "<value or empty to delete>", ...}}
    """
    spec = _provider_or_404(provider)
    _vault_enabled_or_409()

    if not payload.values:
        raise HTTPException(status_code=400, detail="empty_payload")

    known = {f.key_name for f in spec.fields}
    unknown = [k for k in payload.values if k not in known]
    if unknown:
        raise HTTPException(
            status_code=400, detail={"unknown_fields": unknown}
        )

    fields_written: list[str] = []
    fields_deleted: list[str] = []

    for key_name, raw_value in payload.values.items():
        field = spec.field(key_name)
        if field is None:  # pragma: no cover — already filtered above
            continue
        value = raw_value if raw_value is None else raw_value.strip()
        if not value:
            row = _row(session, provider, key_name)
            if row is not None:
                session.delete(row)
                fields_deleted.append(key_name)
                _audit(
                    session,
                    "vault.secret.deleted",
                    provider=provider,
                    key_name=key_name,
                    is_secret=field.is_secret,
                )
            continue

        token = encrypt(value)
        meta = safe_metadata_for(value, is_secret=field.is_secret)
        row = _row(session, provider, key_name)
        if row is None:
            row = IntegrationSecret(
                provider=provider,
                key_name=key_name,
                encrypted_value=token,
                safe_metadata=meta,
                status="configured",
            )
        else:
            row.encrypted_value = token
            row.safe_metadata = meta
            row.status = "configured"
            row.updated_at = utcnow()
        session.add(row)
        fields_written.append(key_name)
        _audit(
            session,
            "vault.secret.saved",
            provider=provider,
            key_name=key_name,
            length=meta.get("length", 0),
            is_secret=field.is_secret,
            source="vault",
        )

    session.commit()

    # Reset the LLM cache whenever an LLM provider's secrets changed.
    if provider in {"anthropic", "openai", "ollama"}:
        llm_registry.reset_provider_cache()

    return _build_summary(session, provider)


@router.delete("/{provider}/{key_name}", response_model=ProviderSummary)
def delete_provider_secret(
    provider: str,
    key_name: str,
    session: Session = Depends(get_session),
) -> ProviderSummary:
    spec = _provider_or_404(provider)
    _vault_enabled_or_409()
    field = spec.field(key_name)
    if field is None:
        raise HTTPException(status_code=404, detail="unknown_key_name")
    row = _row(session, provider, key_name)
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    session.delete(row)
    session.commit()
    _audit(
        session,
        "vault.secret.deleted",
        provider=provider,
        key_name=key_name,
        is_secret=field.is_secret,
    )
    if provider in {"anthropic", "openai", "ollama"}:
        llm_registry.reset_provider_cache()
    return _build_summary(session, provider)


# ---------------------------------------------------------------------------
# Non-publishing test endpoints
# ---------------------------------------------------------------------------


def _probe_outcome(
    key: str,
    label: str,
    status_value: ReadinessStatus,
    *,
    message: str,
    safe_details: dict[str, Any] | None = None,
    severity: ReadinessSeverity | None = None,
) -> ReadinessItem:
    sev_map = {
        ReadinessStatus.VALID: ReadinessSeverity.SUCCESS,
        ReadinessStatus.INVALID: ReadinessSeverity.DANGER,
        ReadinessStatus.ERROR: ReadinessSeverity.DANGER,
        ReadinessStatus.MISSING_CONFIG: ReadinessSeverity.WARNING,
        ReadinessStatus.CONFIGURED: ReadinessSeverity.INFO,
        ReadinessStatus.MOCK: ReadinessSeverity.INFO,
        ReadinessStatus.DISABLED: ReadinessSeverity.INFO,
        ReadinessStatus.UNAVAILABLE: ReadinessSeverity.WARNING,
    }
    return ReadinessItem(
        key=key,
        label=label,
        status=status_value,
        severity=severity or sev_map[status_value],
        message=message[:240],
        safe_details=safe_details or {},
        last_checked_at=utcnow(),
        can_test=True,
    )


def _probe_anthropic(api_key: str, model: str) -> ReadinessItem:
    if not api_key:
        return _probe_outcome(
            "vault.test.anthropic", "Anthropic", ReadinessStatus.MISSING_CONFIG,
            message="No API key resolved (env or vault).",
        )
    try:
        from chief_editor.llm.anthropic_provider import AnthropicProvider

        provider = AnthropicProvider(api_key, model)
        result = provider.complete_json(
            system="You are a JSON-only readiness probe.",
            user='Reply with exactly {"ok": true}.',
            schema={"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}},
            temperature=0,
        )
        ok = bool(result.get("ok"))
        return _probe_outcome(
            "vault.test.anthropic", "Anthropic",
            ReadinessStatus.VALID if ok else ReadinessStatus.INVALID,
            message="Anthropic responded with valid structured JSON." if ok else "Anthropic JSON shape unexpected.",
            safe_details={"model": model},
        )
    except Exception as exc:  # noqa: BLE001
        return _probe_outcome(
            "vault.test.anthropic", "Anthropic", ReadinessStatus.ERROR,
            message=f"Anthropic probe failed: {type(exc).__name__}",
        )


def _probe_openai(api_key: str, model: str) -> ReadinessItem:
    if not api_key:
        return _probe_outcome(
            "vault.test.openai", "OpenAI", ReadinessStatus.MISSING_CONFIG,
            message="No API key resolved (env or vault).",
        )
    try:
        from chief_editor.llm.openai_provider import OpenAIProvider

        provider = OpenAIProvider(api_key, model)
        result = provider.complete_json(
            system="You are a JSON-only readiness probe.",
            user='Reply with exactly {"ok": true}.',
            schema={"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}},
            temperature=0,
        )
        ok = bool(result.get("ok"))
        return _probe_outcome(
            "vault.test.openai", "OpenAI",
            ReadinessStatus.VALID if ok else ReadinessStatus.INVALID,
            message="OpenAI responded with valid structured JSON." if ok else "OpenAI JSON shape unexpected.",
            safe_details={"model": model},
        )
    except Exception as exc:  # noqa: BLE001
        return _probe_outcome(
            "vault.test.openai", "OpenAI", ReadinessStatus.ERROR,
            message=f"OpenAI probe failed: {type(exc).__name__}",
        )


def _is_local(url: str) -> bool:
    u = (url or "").lower()
    return any(h in u for h in ("localhost", "127.0.0.1", "0.0.0.0", "host.docker.internal"))


def _probe_ollama(base_url: str, api_key: str, model: str) -> ReadinessItem:
    if not base_url:
        return _probe_outcome(
            "vault.test.ollama", "Ollama / Kimi K2.6", ReadinessStatus.MISSING_CONFIG,
            message="OLLAMA_BASE_URL is not set (env or vault).",
        )
    effective_key = api_key or ("ollama" if _is_local(base_url) else "")
    if not effective_key:
        return _probe_outcome(
            "vault.test.ollama", "Ollama / Kimi K2.6", ReadinessStatus.MISSING_CONFIG,
            message="OLLAMA_API_KEY is required for remote endpoints.",
        )
    try:
        from chief_editor.llm.ollama_provider import OllamaProvider

        provider = OllamaProvider(base_url=base_url, api_key=effective_key, model=model)
        result = provider.complete_json(
            system="You are a JSON-only readiness probe.",
            user='Reply with exactly {"ok": true, "provider": "ollama"}.',
            schema={
                "type": "object",
                "required": ["ok"],
                "properties": {"ok": {"type": "boolean"}, "provider": {"type": "string"}},
            },
            temperature=0,
        )
        ok = bool(result.get("ok"))
        return _probe_outcome(
            "vault.test.ollama", "Ollama / Kimi K2.6",
            ReadinessStatus.VALID if ok else ReadinessStatus.INVALID,
            message=f"Ollama returned JSON via {model}." if ok else "Ollama JSON shape unexpected.",
            safe_details={"model": model, "is_local": _is_local(base_url)},
        )
    except Exception as exc:  # noqa: BLE001
        return _probe_outcome(
            "vault.test.ollama", "Ollama / Kimi K2.6", ReadinessStatus.ERROR,
            message=f"Ollama probe failed: {type(exc).__name__}",
        )


def _probe_telegram_bot(bot_token: str, target_channel_id: str) -> ReadinessItem:
    """Calls Telegram getMe ONLY — never sendMessage. Read-only by API contract."""
    if not bot_token:
        return _probe_outcome(
            "vault.test.telegram_bot", "Telegram Bot", ReadinessStatus.MISSING_CONFIG,
            message="TELEGRAM_BOT_TOKEN is not set.",
        )
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            bot = data.get("result", {})
            return _probe_outcome(
                "vault.test.telegram_bot", "Telegram Bot", ReadinessStatus.VALID,
                message=f"Bot @{bot.get('username', '?')} responded to getMe.",
                safe_details={
                    "bot_username": bot.get("username"),
                    "target_channel_present": bool(target_channel_id),
                },
            )
        return _probe_outcome(
            "vault.test.telegram_bot", "Telegram Bot", ReadinessStatus.INVALID,
            message=f"Telegram rejected token (HTTP {resp.status_code}).",
        )
    except Exception as exc:  # noqa: BLE001
        return _probe_outcome(
            "vault.test.telegram_bot", "Telegram Bot", ReadinessStatus.ERROR,
            message=f"Telegram getMe failed: {type(exc).__name__}",
        )


def _probe_telethon(api_id: str, api_hash: str) -> ReadinessItem:
    """Telethon needs an interactive login. We verify only that creds are present."""
    if not (api_id and api_hash):
        return _probe_outcome(
            "vault.test.telethon", "Telethon", ReadinessStatus.MISSING_CONFIG,
            message="TELETHON_API_ID and TELETHON_API_HASH are required.",
        )
    return _probe_outcome(
        "vault.test.telethon", "Telethon", ReadinessStatus.CONFIGURED,
        message="Credentials present. Run the CLI runbook to create a session.",
        safe_details={"requires_interactive_session": True},
    )


def _probe_reddit(client_id: str, client_secret: str, user_agent: str) -> ReadinessItem:
    """OAuth client_credentials only — read-only token issuance, never posts."""
    if not (client_id and client_secret):
        return _probe_outcome(
            "vault.test.reddit", "Reddit", ReadinessStatus.MISSING_CONFIG,
            message="REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are required.",
        )
    try:
        auth = httpx.BasicAuth(client_id, client_secret)
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(
                "https://www.reddit.com/api/v1/access_token",
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": user_agent or "ai-chief-editor-os-dev"},
                auth=auth,
            )
        if resp.status_code == 200 and resp.json().get("access_token"):
            return _probe_outcome(
                "vault.test.reddit", "Reddit", ReadinessStatus.VALID,
                message="Reddit issued an access token (read-only API ready).",
            )
        return _probe_outcome(
            "vault.test.reddit", "Reddit", ReadinessStatus.INVALID,
            message=f"Reddit rejected credentials (HTTP {resp.status_code}).",
        )
    except Exception as exc:  # noqa: BLE001
        return _probe_outcome(
            "vault.test.reddit", "Reddit", ReadinessStatus.ERROR,
            message=f"Reddit probe failed: {type(exc).__name__}",
        )


def _probe_postiz(base_url: str, api_key: str) -> ReadinessItem:
    """Postiz read-only probe — tries /api/integrations and /api/posts?limit=1.

    Never creates posts. Per docs/SAFETY_MODEL.md.
    """
    if not (base_url and api_key):
        return _probe_outcome(
            "vault.test.postiz", "Postiz", ReadinessStatus.MISSING_CONFIG,
            message="POSTIZ_BASE_URL and POSTIZ_API_KEY are required.",
        )
    base = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    last_status = None
    last_err = None
    for path in ("/api/v1/integrations", "/api/integrations", "/api/posts?limit=1"):
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{base}{path}", headers=headers)
            last_status = resp.status_code
            if resp.status_code < 400:
                return _probe_outcome(
                    "vault.test.postiz", "Postiz", ReadinessStatus.VALID,
                    message=f"Postiz responded {resp.status_code} on {path}.",
                    safe_details={"probe_path": path, "probe_status": resp.status_code},
                )
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"[:120]
            continue
    return _probe_outcome(
        "vault.test.postiz", "Postiz", ReadinessStatus.INVALID,
        message=f"Postiz did not respond to read probes. Last status={last_status}; err={last_err}",
    )


_PROBE_DISPATCH = {
    "anthropic": lambda r: _probe_anthropic(
        r["api_key"].value or "",
        r["model"].value or get_settings().anthropic_model,
    ),
    "openai": lambda r: _probe_openai(
        r["api_key"].value or "",
        r["model"].value or get_settings().openai_model,
    ),
    "ollama": lambda r: _probe_ollama(
        r["base_url"].value or "",
        r["api_key"].value or "",
        r["model"].value or get_settings().ollama_model,
    ),
    "telegram_bot": lambda r: _probe_telegram_bot(
        r["bot_token"].value or "",
        r["target_channel_id"].value or "",
    ),
    "telethon": lambda r: _probe_telethon(
        r["api_id"].value or "",
        r["api_hash"].value or "",
    ),
    "reddit": lambda r: _probe_reddit(
        r["client_id"].value or "",
        r["client_secret"].value or "",
        r["user_agent"].value or get_settings().reddit_user_agent,
    ),
    "postiz": lambda r: _probe_postiz(
        r["base_url"].value or "",
        r["api_key"].value or "",
    ),
}


@router.post("/{provider}/test", response_model=ReadinessItem)
def test_provider(
    provider: str,
    session: Session = Depends(get_session),
) -> ReadinessItem:
    spec = _provider_or_404(provider)
    # Note: test is permitted even when vault is disabled — it still uses
    # env credentials. The mock LLM also runs unconditionally; this endpoint
    # never publishes, only probes identity / read endpoints.
    resolved = resolve_provider(provider, session=session)
    probe = _PROBE_DISPATCH.get(provider)
    if probe is None:
        raise HTTPException(status_code=400, detail="unsupported_test_provider")

    item = probe(resolved)
    item.label = f"Vault test — {spec.label}"

    # Record per-row status updates if vault rows exist for this provider.
    if is_vault_enabled():
        try:
            now = utcnow()
            for row in _rows_for(session, provider):
                row.status = item.status.value
                row.last_tested_at = now
                row.last_test_message = (item.message or "")[:240]
                row.updated_at = now
                session.add(row)
            session.commit()
        except (KeyRotationError, VaultDisabledError):
            session.rollback()

    _audit(
        session,
        "vault.secret.tested",
        provider=provider,
        status=item.status.value,
        source=_aggregate([rf.source for rf in resolved.values()]),
    )

    if provider in {"anthropic", "openai", "ollama"}:
        # After a successful real-credential test, drop the LLM cache so the
        # next get_llm_provider() rebuilds with the fresh credentials.
        llm_registry.reset_provider_cache()

    return item
