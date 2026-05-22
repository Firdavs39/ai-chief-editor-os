"""Phase 7 — collector safety AST guards.

Verifies, via AST inspection of the actual collector source files, that
read-only collectors never call platform write-APIs. This is defense-in-
depth: even if someone (human or AI) tries to add a "convenience" send
call later, this test makes it a build failure.
"""
from __future__ import annotations

import ast
import inspect

# Telegram (Telethon) write methods that must never appear in our collector.
TELETHON_FORBIDDEN_METHODS = {
    "send_message",
    "send_file",
    "send_read_acknowledge",
    "edit_message",
    "delete_messages",
    "forward_messages",
    "pin_message",
    "unpin_message",
    "kick_participant",
    "ban_chatmember",  # variant
    "leave_channel",
    "edit_admin",
    "edit_permissions",
}

# Reddit (PRAW / asyncpraw) write methods that must never appear in our collector.
REDDIT_FORBIDDEN_METHODS = {
    "submit",
    "reply",
    "upvote",
    "downvote",
    "clear_vote",
    "delete",
    "edit",
    "save",
    "unsave",
    "hide",
    "unhide",
    "report",
    "mod",  # accessing .mod can mutate
    "approve",
    "remove",
    "ban",
    "send_message",
    "compose_message",
}


def _all_attribute_call_names(tree: ast.AST) -> set[str]:
    """Return the set of attribute names appearing as `.attr(...)` in any
    function-call expression. Catches direct method calls on any object."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _module_source(module_path: str) -> str:
    mod = __import__(module_path, fromlist=["__name__"])
    return inspect.getsource(mod)


def test_telegram_collector_calls_no_write_api() -> None:
    src = _module_source("chief_editor.collectors.telegram")
    called = _all_attribute_call_names(ast.parse(src))
    leaked = called & TELETHON_FORBIDDEN_METHODS
    assert not leaked, (
        f"telegram collector calls forbidden Telethon write methods: {leaked}. "
        f"Telethon is read-only in this product. If you need to send, use "
        f"the publisher (which is gated behind PUBLISHING_ENABLED + "
        f"DRY_RUN_PUBLISH + approval). Never from a collector."
    )


def test_reddit_collector_calls_no_write_api() -> None:
    src = _module_source("chief_editor.collectors.reddit")
    called = _all_attribute_call_names(ast.parse(src))
    leaked = called & REDDIT_FORBIDDEN_METHODS
    assert not leaked, (
        f"reddit collector calls forbidden write methods: {leaked}. "
        f"Reddit access is read-only in this product."
    )


def test_no_collector_imports_publisher() -> None:
    """Defense-in-depth: collectors must NOT import publishers, ever.
    A collector importing a publisher means the layering broke and the
    'collector never publishes' invariant is at risk."""
    import importlib
    import pkgutil

    import chief_editor.collectors as collectors_pkg

    for mod_info in pkgutil.iter_modules(collectors_pkg.__path__):
        mod = importlib.import_module(f"chief_editor.collectors.{mod_info.name}")
        src = inspect.getsource(mod)
        # Plain substring check is enough — `from .publishers` or
        # `import chief_editor.publishers` both contain "publishers".
        assert "chief_editor.publishers" not in src, (
            f"collector {mod_info.name} imports a publisher — "
            f"layering violation"
        )
        assert ".publishers" not in src or "from ." not in src, (
            f"collector {mod_info.name} imports from publishers — "
            f"layering violation"
        )


def test_telegram_collector_uses_iter_messages_only() -> None:
    """Positive check: confirm Telethon usage is iter_messages (read-only
    cursor) rather than any other API. Lock in the pattern."""
    src = _module_source("chief_editor.collectors.telegram")
    assert "iter_messages" in src, (
        "telegram collector should use iter_messages — the read-only Telethon API"
    )


def test_telethon_session_creator_does_not_send() -> None:
    """The session-builder script must not invoke any send method.
    Defense-in-depth around the helper that builds the credential.

    Scripts live outside the importable package tree, so we read the file
    by path rather than importing.
    """
    from pathlib import Path

    script_path = Path(__file__).resolve().parents[1] / "scripts" / "create_telethon_session.py"
    src = script_path.read_text(encoding="utf-8")
    called = _all_attribute_call_names(ast.parse(src))
    leaked = called & TELETHON_FORBIDDEN_METHODS
    assert not leaked, (
        f"create_telethon_session script calls forbidden methods: {leaked}"
    )
