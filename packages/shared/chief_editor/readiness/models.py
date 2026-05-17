"""Pydantic models for the readiness report.

These are the *only* shapes returned from /readiness and friends — they
intentionally cannot carry secret values:
- `safe_details` is a free-form dict but callers must never put secrets in it
- `missing_env_vars` is a list of variable *names* only
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReadinessStatus(str, Enum):
    MOCK = "mock"
    MISSING_CONFIG = "missing_config"
    CONFIGURED = "configured"
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class ReadinessSeverity(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"


class ReadinessItem(BaseModel):
    key: str
    label: str
    status: ReadinessStatus
    severity: ReadinessSeverity = ReadinessSeverity.INFO
    message: str = ""
    missing_env_vars: list[str] = Field(default_factory=list)
    safe_details: dict[str, Any] = Field(default_factory=dict)
    last_checked_at: datetime | None = None
    can_test: bool = False
    docs_hint: str = ""
    next_action: str = ""


class ReadinessSection(BaseModel):
    key: str
    label: str
    items: list[ReadinessItem] = Field(default_factory=list)


class ModeFlags(BaseModel):
    app_env: str
    mock_mode: bool
    demo_mode: bool
    live_mode: bool
    dry_run_publish: bool
    publishing_enabled: bool


class ReadinessReport(BaseModel):
    generated_at: datetime
    mode: ModeFlags
    sections: list[ReadinessSection] = Field(default_factory=list)
    overall_score: int = 0  # 0-100, % of items in {valid, configured, mock}
    overall_label: str = "demo"


def severity_for(status: ReadinessStatus) -> ReadinessSeverity:
    """Default severity mapping for a status."""
    mapping = {
        ReadinessStatus.MOCK: ReadinessSeverity.INFO,
        ReadinessStatus.MISSING_CONFIG: ReadinessSeverity.WARNING,
        ReadinessStatus.CONFIGURED: ReadinessSeverity.INFO,
        ReadinessStatus.VALID: ReadinessSeverity.SUCCESS,
        ReadinessStatus.INVALID: ReadinessSeverity.DANGER,
        ReadinessStatus.ERROR: ReadinessSeverity.DANGER,
        ReadinessStatus.DISABLED: ReadinessSeverity.INFO,
        ReadinessStatus.UNAVAILABLE: ReadinessSeverity.WARNING,
    }
    return mapping[status]
