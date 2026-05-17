"""Integration Secrets Vault — encrypted-at-rest credential storage.

Public surface:

    is_vault_enabled() -> bool
    encrypt(value) -> token
    decrypt(token) -> value          # backend-only; never returned via API
    rotate_token(token) -> new_token
    generate_key() -> str
    mask(value, keep=4) -> str
    safe_metadata_for(value, *, is_secret) -> dict
    constant_time_eq(a, b) -> bool   # admin-token compare

    PROVIDER_SPECS, get_provider_spec, FieldSpec, ProviderSpec
    VaultDisabledError, KeyRotationError
"""

from __future__ import annotations

from .crypto import (
    KeyRotationError,
    VaultDisabledError,
    constant_time_eq,
    decrypt,
    encrypt,
    generate_key,
    is_vault_enabled,
    mask,
    rotate_token,
    safe_metadata_for,
)
from .schemas import (
    PROVIDER_SPECS,
    SUPPORTED_PROVIDERS,
    FieldSpec,
    ProviderSpec,
    get_provider_spec,
)

__all__ = [
    "PROVIDER_SPECS",
    "SUPPORTED_PROVIDERS",
    "FieldSpec",
    "KeyRotationError",
    "ProviderSpec",
    "VaultDisabledError",
    "constant_time_eq",
    "decrypt",
    "encrypt",
    "generate_key",
    "get_provider_spec",
    "is_vault_enabled",
    "mask",
    "rotate_token",
    "safe_metadata_for",
]
