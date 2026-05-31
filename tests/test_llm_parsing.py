"""LLMProvider._safe_parse — JSON parsing + tolerant repair.

The base provider escalates tolerance only when strict parsing fails:
  - clean JSON → parses
  - JSON embedded in prose / markdown fences → extracts outermost {...}
  - messy-but-recoverable (truncated, unescaped quotes, trailing commas,
    unquoted keys) → json_repair rescues it
  - genuine garbage / pure prose / empty → None

The repair stage was added after real Kimi runs intermittently returned
JSON that strict parsing rejected (a long writer step would burn ~30 min
then fail the whole run on one malformed character). Repair only runs as a
last resort, so it can rescue a doomed call but never degrade a valid one;
the downstream pydantic validator still enforces the schema shape.
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


def test_repairs_malformed_brace_block() -> None:
    # Unquoted key + trailing comma — json_repair rescues this now (it used
    # to return None). This is the intended tolerant behavior.
    assert _parse("response: {invalid: yes,}") == {"invalid": "yes"}


def test_returns_none_for_inverted_braces() -> None:
    # `}` before `{` — no recoverable object; repair yields nothing.
    assert _parse("} something {") is None


def test_repairs_takes_outermost_braces_not_inner() -> None:
    # We take the last `}` so inner objects are preserved.
    raw = 'prefix {"outer": {"inner": 1}} suffix'
    assert _parse(raw) == {"outer": {"inner": 1}}


# --- Repair-stage rescues (real Kimi failure modes) ----------------------


def test_repairs_truncated_json() -> None:
    # Output cut off mid-string (hit token cap / model stopped). The strict
    # passes fail; repair closes the open structure.
    raw = '{"hook": "Salom", "body": "juda uzun matn obrezalo'
    parsed = _parse(raw)
    assert isinstance(parsed, dict)
    assert parsed.get("hook") == "Salom"


def test_repairs_unescaped_quotes_in_string() -> None:
    # Model put literal quotes inside a value without escaping them.
    raw = '{"hook": "bu "yangi" trick", "body": "matn", "cta": "bos"}'
    parsed = _parse(raw)
    assert isinstance(parsed, dict)
    assert "body" in parsed and "cta" in parsed


def test_repairs_markdown_fenced_json() -> None:
    raw = '```json\n{"hook": "x", "body": "y", "cta": "z"}\n```'
    assert _parse(raw) == {"hook": "x", "body": "y", "cta": "z"}
