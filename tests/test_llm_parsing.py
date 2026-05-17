"""LLMProvider._safe_parse — JSON parsing + minimal repair.

The base provider tolerates LLMs that wrap JSON in prose:
  - clean JSON → parses
  - JSON embedded in prose → extracts the outermost {...} substring
  - garbage → None
  - JSON-shaped but invalid → None (no infinite recovery)

Anthropic/OpenAI providers rely on this to either accept the first response
or retry once before raising. Mock provider always returns clean JSON.
"""

from __future__ import annotations

from chief_editor.llm.base import LLMProvider


class _StubProvider(LLMProvider):
    """Minimal concrete subclass so we can call the protected _safe_parse."""

    name = "stub"

    def complete_json(self, system, user, schema, *, temperature=0.7):
        raise NotImplementedError

    def rewrite(self, text, mode):
        raise NotImplementedError


def _parse(raw: str):
    return _StubProvider()._safe_parse(raw)


def test_parses_clean_json() -> None:
    assert _parse('{"ok": true}') == {"ok": True}


def test_parses_nested_clean_json() -> None:
    assert _parse('{"x": {"y": [1, 2, 3]}, "z": null}') == {"x": {"y": [1, 2, 3]}, "z": None}


def test_repairs_prose_wrapped_json() -> None:
    raw = "Here is the JSON you asked for:\n\n{\"ok\": true, \"n\": 42}\n\nLet me know if anything is wrong."
    assert _parse(raw) == {"ok": True, "n": 42}


def test_repairs_json_with_trailing_explanation() -> None:
    raw = '{"ok": true} — and that\'s the answer.'
    assert _parse(raw) == {"ok": True}


def test_returns_none_for_empty_string() -> None:
    assert _parse("") is None


def test_returns_none_for_pure_prose() -> None:
    assert _parse("I cannot comply with that request.") is None


def test_returns_none_for_malformed_brace_block() -> None:
    # Looks like JSON but isn't valid.
    assert _parse("response: {invalid: yes,}") is None


def test_returns_none_for_inverted_braces() -> None:
    # `}` before `{` — extraction guard.
    assert _parse("} something {") is None


def test_repairs_takes_outermost_braces_not_inner() -> None:
    # We take the last `}` so inner objects are preserved.
    raw = 'prefix {"outer": {"inner": 1}} suffix'
    assert _parse(raw) == {"outer": {"inner": 1}}
