"""Fernet/MultiFernet encryption for the Integration Secrets Vault.

We use `cryptography.fernet.Fernet` — AES-128-CBC + HMAC-SHA256 + version
byte + IV + timestamp — wrapped in `MultiFernet` so key rotation is a
one-line config change. Never invent crypto here.

Rules:
- `encrypt("")` raises — empty values are data corruption.
- `decrypt(token)` raises `KeyRotationError` on `InvalidToken`. Callers
  must treat that as "field is unreadable" and downgrade to missing.
- `_get_cipher()` reads from `Settings`; it does not cache, because the
  key may legitimately change at runtime (rotation, test setup).
- This module never logs values or tokens.
"""

from __future__ import annotations

import secrets as stdlib_secrets

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from ...settings import get_settings


class VaultDisabledError(RuntimeError):
    """Raised when an encryption operation is attempted without a master key."""


class KeyRotationError(RuntimeError):
    """Raised when a token cannot be decrypted with any configured key."""


def is_vault_enabled() -> bool:
    """True iff a primary MASTER_ENCRYPTION_KEY is configured and parsable."""
    s = get_settings()
    if not s.master_encryption_key:
        return False
    try:
        Fernet(s.master_encryption_key.encode("utf-8"))
    except (ValueError, TypeError):
        return False
    return True


def _build_keys() -> list[Fernet]:
    s = get_settings()
    keys: list[Fernet] = []
    if s.master_encryption_key:
        keys.append(Fernet(s.master_encryption_key.encode("utf-8")))
    for legacy in s.legacy_encryption_keys:
        try:
            keys.append(Fernet(legacy.encode("utf-8")))
        except (ValueError, TypeError):
            # Skip malformed legacy entries — explicit log happens at call site.
            continue
    return keys


def _get_cipher() -> MultiFernet:
    keys = _build_keys()
    if not keys:
        raise VaultDisabledError(
            "MASTER_ENCRYPTION_KEY is not set or is invalid; vault is disabled."
        )
    return MultiFernet(keys)


def encrypt(value: str) -> str:
    """Encrypt a string value. Returns a url-safe base64 Fernet token."""
    if value is None or value == "":
        raise ValueError("Cannot encrypt an empty value")
    cipher = _get_cipher()
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token previously produced by encrypt().

    Raises KeyRotationError if no configured key can decrypt the token.
    """
    cipher = _get_cipher()
    try:
        return cipher.decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise KeyRotationError(
            "Stored token cannot be decrypted with any configured key"
        ) from exc


def rotate_token(token: str) -> str:
    """Re-encrypt a token with the current primary key.

    Used by the `rotate-key` CLI to roll old ciphertexts forward in place.
    """
    cipher = _get_cipher()
    try:
        return cipher.rotate(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise KeyRotationError(
            "Stored token cannot be re-encrypted with current keys"
        ) from exc


def generate_key() -> str:
    """Produce a fresh, valid MASTER_ENCRYPTION_KEY value."""
    return Fernet.generate_key().decode("utf-8")


def mask(value: str, *, keep: int = 4) -> str:
    """Produce a UI-safe preview of a secret value.

    Reveals at most `keep` trailing characters. For short values, masks
    everything to avoid leaking near-complete tokens.
    """
    if not value:
        return ""
    if len(value) <= keep * 2:
        return "…" * 3
    return "…" + value[-keep:]


def safe_metadata_for(value: str, *, is_secret: bool) -> dict:
    """Build the per-row `safe_metadata` payload for storage + UI display.

    Secret fields surface only length + mask. Non-secret fields surface the
    plaintext value (it is not sensitive by definition of the schema).
    """
    if is_secret:
        return {
            "is_secret": True,
            "length": len(value),
            "mask": mask(value),
        }
    return {
        "is_secret": False,
        "length": len(value),
        "value": value,
    }


def constant_time_eq(a: str, b: str) -> bool:
    """Constant-time string comparison wrapper.

    Imported as `stdlib_secrets` to avoid collision with our package.
    """
    return stdlib_secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
