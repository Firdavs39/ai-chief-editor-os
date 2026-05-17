"""Encryption layer tests for the Integration Secrets Vault."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from chief_editor.services.secrets import (
    KeyRotationError,
    VaultDisabledError,
    decrypt,
    encrypt,
    generate_key,
    is_vault_enabled,
    mask,
    rotate_token,
    safe_metadata_for,
)
from chief_editor.settings import get_settings


def test_encrypt_decrypt_roundtrip() -> None:
    token = encrypt("sk-ant-test-value-1234567890")
    assert token != "sk-ant-test-value-1234567890"
    assert decrypt(token) == "sk-ant-test-value-1234567890"


def test_encrypt_rejects_empty_string() -> None:
    with pytest.raises(ValueError):
        encrypt("")


def test_mask_keeps_only_last_four() -> None:
    assert mask("sk-ant-abcdefghij") == "…ghij"
    # Short values are fully masked.
    assert mask("abcd") == "…" * 3


def test_safe_metadata_for_secret_has_no_value() -> None:
    meta = safe_metadata_for("super-secret-token-xyz", is_secret=True)
    assert meta["is_secret"] is True
    assert "value" not in meta
    assert meta["mask"].endswith("xyz") or meta["mask"] == "…" * 3
    assert meta["length"] == len("super-secret-token-xyz")


def test_safe_metadata_for_non_secret_keeps_value() -> None:
    meta = safe_metadata_for("kimi-k2.6:cloud", is_secret=False)
    assert meta["value"] == "kimi-k2.6:cloud"
    assert meta["is_secret"] is False


def test_missing_master_key_disables_vault(monkeypatch) -> None:
    # Empty-string env var overrides any .env value (pydantic-settings reads
    # env > .env). Using delenv alone is not enough once .env has a real key.
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "")
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYS_LEGACY", "")
    get_settings.cache_clear()
    assert is_vault_enabled() is False
    with pytest.raises(VaultDisabledError):
        encrypt("anything")


def test_invalid_master_key_disables_vault(monkeypatch) -> None:
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", "not-a-real-fernet-key")
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYS_LEGACY", "")
    get_settings.cache_clear()
    assert is_vault_enabled() is False


def test_multifernet_reads_with_legacy_key(monkeypatch) -> None:
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()

    # Encrypt with the OLD key in a temporary setup.
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", old_key)
    monkeypatch.delenv("MASTER_ENCRYPTION_KEYS_LEGACY", raising=False)
    get_settings.cache_clear()
    legacy_token = encrypt("legacy-payload")

    # Now flip to the new key with the old one demoted to legacy.
    monkeypatch.setenv("MASTER_ENCRYPTION_KEY", new_key)
    monkeypatch.setenv("MASTER_ENCRYPTION_KEYS_LEGACY", old_key)
    get_settings.cache_clear()

    # MultiFernet should still decrypt with the legacy key.
    assert decrypt(legacy_token) == "legacy-payload"

    # And rotate_token() re-encrypts with the new primary.
    rotated = rotate_token(legacy_token)
    assert rotated != legacy_token

    # Drop the legacy key — rotated token still decrypts; original no longer does.
    monkeypatch.delenv("MASTER_ENCRYPTION_KEYS_LEGACY")
    get_settings.cache_clear()
    assert decrypt(rotated) == "legacy-payload"
    with pytest.raises(KeyRotationError):
        decrypt(legacy_token)


def test_generate_key_is_valid_fernet_key() -> None:
    k = generate_key()
    # Constructor accepts the produced value.
    Fernet(k.encode())
