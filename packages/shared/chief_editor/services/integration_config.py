"""Env-first, vault-fallback credential resolver.

Resolution order for any field:
    1. ENV var (via Settings attribute or os.environ) — highest priority
    2. IntegrationSecret row (decrypted) — when env is empty
    3. (None, "missing") — neither configured

The resolver is a *read-only* helper. It never writes, never logs values,
and never raises on missing configuration. Decrypt failures (e.g. master
key changed without rotation) are downgraded to "missing" so a single bad
row never breaks the provider.

Callers in FastAPI routes should pass their existing session via `session=`
to avoid double-opening. Workers and registries can omit it; the resolver
opens a short-lived `session_scope()` on demand.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session, select

from ..db import session_scope
from ..models import IntegrationSecret
from ..settings import Settings, get_settings
from .secrets import (
    KeyRotationError,
    VaultDisabledError,
    decrypt,
    is_vault_enabled,
)
from .secrets.schemas import PROVIDER_SPECS, FieldSpec, ProviderSpec, get_provider_spec

log = logging.getLogger("chief_editor.integration_config")

Source = Literal["env", "vault", "missing"]


@dataclass(frozen=True)
class ResolvedField:
    key_name: str
    value: str | None
    source: Source


def _settings_env_value(settings: Settings, env_var: str) -> str:
    """Look up the env var via Settings (case-insensitive lower_snake attr)."""
    attr = env_var.lower()
    raw = getattr(settings, attr, None)
    if raw is None:
        return ""
    return str(raw).strip()


def _vault_value(session: Session, provider: str, key_name: str) -> str | None:
    row = session.exec(
        select(IntegrationSecret).where(
            IntegrationSecret.provider == provider,
            IntegrationSecret.key_name == key_name,
        )
    ).first()
    if row is None:
        return None
    try:
        return decrypt(row.encrypted_value)
    except (KeyRotationError, VaultDisabledError):
        log.warning(
            "vault decrypt failed; downgrading to missing",
            extra={"provider": provider, "key_name": key_name},
        )
        return None


def _resolve_one(
    session: Session, settings: Settings, spec: ProviderSpec, field: FieldSpec
) -> ResolvedField:
    env_value = _settings_env_value(settings, field.env_var)
    if env_value:
        return ResolvedField(key_name=field.key_name, value=env_value, source="env")

    if is_vault_enabled():
        vault_value = _vault_value(session, spec.provider, field.key_name)
        if vault_value:
            return ResolvedField(
                key_name=field.key_name, value=vault_value, source="vault"
            )

    return ResolvedField(key_name=field.key_name, value=None, source="missing")


def resolve_field(
    provider: str, key_name: str, *, session: Session | None = None
) -> ResolvedField:
    spec = get_provider_spec(provider)
    field = spec.field(key_name)
    if field is None:
        raise KeyError(f"unknown key_name '{key_name}' for provider '{provider}'")
    settings = get_settings()
    if session is not None:
        return _resolve_one(session, settings, spec, field)
    with session_scope() as s:
        return _resolve_one(s, settings, spec, field)


def resolve_provider(
    provider: str, *, session: Session | None = None
) -> dict[str, ResolvedField]:
    spec = get_provider_spec(provider)
    settings = get_settings()
    if session is not None:
        return {
            f.key_name: _resolve_one(session, settings, spec, f) for f in spec.fields
        }
    with session_scope() as s:
        return {f.key_name: _resolve_one(s, settings, spec, f) for f in spec.fields}


def field_source(
    provider: str, key_name: str, *, session: Session | None = None
) -> Source:
    """Cheap check of where a field would resolve from (no value returned)."""
    spec = get_provider_spec(provider)
    field = spec.field(key_name)
    if field is None:
        return "missing"
    settings = get_settings()
    if _settings_env_value(settings, field.env_var):
        return "env"
    if not is_vault_enabled():
        return "missing"
    if session is not None:
        return "vault" if _vault_value(session, provider, key_name) else "missing"
    with session_scope() as s:
        return "vault" if _vault_value(s, provider, key_name) else "missing"


__all__ = [
    "PROVIDER_SPECS",
    "ResolvedField",
    "Source",
    "field_source",
    "resolve_field",
    "resolve_provider",
]
