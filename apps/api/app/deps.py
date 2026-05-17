"""FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Header, HTTPException, Request
from sqlmodel import Session

from chief_editor.db import get_session as _get_session
from chief_editor.services.secrets import constant_time_eq
from chief_editor.settings import Settings, get_settings

# Loopback hostnames that are considered "strictly local" for the admin-token
# dev exemption. Anything else MUST present a valid X-Admin-Token.
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}

_LOCAL_FRONTEND_PREFIXES = (
    "http://localhost",
    "http://127.0.0.1",
    "https://localhost",
    "https://127.0.0.1",
)


def get_session() -> Generator[Session, None, None]:
    yield from _get_session()


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    # Strip optional :port — TestClient may send "testserver" so we never
    # treat that as loopback either.
    h = host.split(":", 1)[0].lower()
    return h in _LOOPBACK_HOSTS


def _frontend_origin_is_local_only(settings: Settings) -> bool:
    raw = (settings.frontend_origin or "").strip()
    if not raw:
        # Empty FRONTEND_ORIGIN is "*" in dev only — not safe to count as local.
        return False
    origins = [o.strip().lower() for o in raw.split(",") if o.strip()]
    if not origins:
        return False
    return all(o.startswith(_LOCAL_FRONTEND_PREFIXES) for o in origins)


def _is_strictly_local_dev(request: Request, settings: Settings) -> bool:
    """Return True if every condition for the no-token dev exemption holds.

    Mirrors the policy in docs/SECRETS_VAULT.md. ANY violation defaults to
    "require token" — there is no partial credit.
    """
    if settings.app_env != "dev":
        return False
    if settings.live_mode:
        return False
    if (settings.public_api_url or "").strip():
        return False
    if not _is_loopback_host(request.client.host if request.client else None):
        return False
    if not _is_loopback_host(_extract_host_header(request)):
        return False
    frontend = (settings.frontend_origin or "").strip()
    return not (frontend and not _frontend_origin_is_local_only(settings))


def _extract_host_header(request: Request) -> str | None:
    host = request.headers.get("host")
    if not host:
        return None
    return host


def require_admin_token(
    request: Request,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """Authorize a /secrets/* request.

    Rules:
    - If ADMIN_TOKEN is set: header MUST match in constant time.
    - If ADMIN_TOKEN is empty AND the request is strictly local dev (see
      `_is_strictly_local_dev`): allow with a no-op.
    - Otherwise: 401.

    Constant-time compare uses `secrets.compare_digest` (imported as
    `stdlib_secrets` inside the crypto helper) to avoid timing attacks.
    """
    settings = get_settings()
    expected = (settings.admin_token or "").strip()

    if expected:
        provided = (x_admin_token or "").strip()
        # Always do the compare so timing is uniform even when no header was sent.
        if not provided or not constant_time_eq(provided, expected):
            raise HTTPException(status_code=401, detail="admin_token_required")
        return

    # ADMIN_TOKEN is empty. Only the strictly-local dev path is allowed.
    if _is_strictly_local_dev(request, settings):
        return
    raise HTTPException(
        status_code=401,
        detail="admin_token_required_in_non_local_context",
    )


__all__ = ["get_session", "require_admin_token"]


# Internal exports for unit testing of the gate.
def _expose_for_tests() -> dict:
    return {
        "is_loopback_host": _is_loopback_host,
        "is_strictly_local_dev": _is_strictly_local_dev,
        "frontend_origin_is_local_only": _frontend_origin_is_local_only,
        "_extract_host_header": _extract_host_header,
    }
