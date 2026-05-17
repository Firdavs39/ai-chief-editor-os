"""IntegrationSecret — encrypted-at-rest storage for vault entries.

One row per (provider, key_name). The plaintext value lives only inside
`encrypted_value` (a Fernet token). `safe_metadata` is a small JSON dict
the API can return to the frontend without leaking the underlying value.

There is intentionally no `is_secret` column — sensitivity is a property
of the field schema, not the stored value. Drift between code and DB on
that flag would be catastrophic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from ._base import TimestampedBase, json_column


class IntegrationSecret(TimestampedBase, table=True):
    __tablename__ = "integration_secrets"
    __table_args__ = (
        UniqueConstraint("provider", "key_name", name="uq_integration_provider_key"),
    )

    provider: str = Field(index=True, max_length=64)
    key_name: str = Field(max_length=64)
    encrypted_value: str = Field()
    safe_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=json_column())
    status: str = Field(default="unknown", max_length=32)
    last_tested_at: datetime | None = Field(default=None)
    last_test_message: str = Field(default="", max_length=240)
