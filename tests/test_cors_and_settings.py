"""Production-readiness settings tests.

These verify three things:
  1. The new env-driven CORS allow-list parses correctly.
  2. Safety flag defaults stay safe (no accidental publishing).
  3. The logging configurator can be imported and called without secrets leaking.
"""

from __future__ import annotations

from chief_editor.settings import Settings


def test_cors_origins_defaults_to_wildcard_in_dev() -> None:
    s = Settings(_env_file=None)
    assert s.cors_origins == ["*"]


def test_cors_origins_parses_comma_separated() -> None:
    s = Settings(_env_file=None, frontend_origin="https://a.example, https://b.example")
    assert s.cors_origins == ["https://a.example", "https://b.example"]


def test_cors_origins_strips_blank_segments() -> None:
    s = Settings(_env_file=None, frontend_origin="https://a.example,,  ,https://b.example  ")
    assert s.cors_origins == ["https://a.example", "https://b.example"]


def test_safety_flag_defaults_are_safe() -> None:
    """Nothing should be able to publish without operator opt-in."""
    s = Settings(_env_file=None)
    # The narrow path to a real publish:
    #   publishing_enabled=true AND dry_run_publish=false AND approval=approve
    # Defaults must not satisfy that.
    real_publish_possible = s.publishing_enabled and not s.dry_run_publish
    assert real_publish_possible is False, (
        "Default settings must not allow real publishing. "
        f"publishing_enabled={s.publishing_enabled} dry_run_publish={s.dry_run_publish}"
    )


def test_public_api_url_and_frontend_origin_default_empty() -> None:
    s = Settings(_env_file=None)
    assert s.public_api_url == ""
    assert s.frontend_origin == ""


def test_logging_configurator_redacts_secret_keys() -> None:
    """The structlog processor must mask anything that looks like a secret."""
    from chief_editor.logging_config import _redact

    event = {
        "msg": "boot",
        "anthropic_api_key": "sk-ant-VERY-SECRET-VALUE",
        "telegram_bot_token": "12345:AAAAAA",
        "ordinary_field": "hello",
    }
    out = _redact(None, None, dict(event))
    assert out["msg"] == "boot"
    assert out["ordinary_field"] == "hello"
    assert "VERY-SECRET-VALUE" not in str(out)
    assert "12345" not in str(out)
    assert out["anthropic_api_key"].startswith("<redacted")
    assert out["telegram_bot_token"].startswith("<redacted")


def test_logging_configurator_idempotent() -> None:
    """configure_logging() should not throw on second call."""
    from chief_editor.logging_config import configure_logging

    configure_logging(service="test")
    configure_logging(service="test")  # second call is a no-op
