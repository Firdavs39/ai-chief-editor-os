"""Anthropic + OpenAI providers tested with fully mocked SDK clients.

These tests must never reach the network. They verify:
- successful structured-JSON completion is parsed and returned
- malformed JSON triggers the one-retry path; persistent failure raises ValueError
- the prompt sent to the underlying client contains both the user input and
  the requested schema (so the model has a chance to comply)
- rewrite() returns the text portion of the response

Mocking strategy: instantiate the provider with a placeholder API key, then
replace its `_client` attribute with a fake object that records calls and
returns canned responses.
"""

from __future__ import annotations

import pytest

from chief_editor.llm.anthropic_provider import AnthropicProvider
from chief_editor.llm.openai_provider import OpenAIProvider

# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class _AContent:
    def __init__(self, text: str) -> None:
        self.text = text


class _AResponse:
    def __init__(self, text: str) -> None:
        self.content = [_AContent(text)]


class _AMessages:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(kw)
        if not self._responses:
            raise AssertionError("provider called create() more times than mocked responses")
        return _AResponse(self._responses.pop(0))


class _AClient:
    def __init__(self, responses: list[str]) -> None:
        self.messages = _AMessages(responses)


def _anthropic(responses: list[str]) -> AnthropicProvider:
    p = AnthropicProvider("sk-ant-placeholder", model="claude-test")
    p._client = _AClient(responses)
    return p


def test_anthropic_complete_json_returns_parsed_dict() -> None:
    p = _anthropic(['{"ok": true, "topic": "x"}'])
    out = p.complete_json("sys", "тема: x", {"type": "object"})
    assert out == {"ok": True, "topic": "x"}
    assert p._client.messages.calls, "Anthropic client must be invoked"


def test_anthropic_prompt_includes_user_and_schema() -> None:
    p = _anthropic(['{"x": 1}'])
    p.complete_json("you are sys", "тема: trends", {"type": "object", "required": ["x"]})
    sent = p._client.messages.calls[0]
    assert sent["system"] == "you are sys"
    assert sent["model"] == "claude-test"
    user_msg = sent["messages"][0]["content"]
    assert "тема: trends" in user_msg
    assert "STRICT JSON" in user_msg
    assert '"required":' in user_msg


def test_anthropic_repairs_prose_wrapped_json_without_retry() -> None:
    p = _anthropic(['Sure! Here is the JSON:\n{"ok": true}\nLet me know.'])
    out = p.complete_json("s", "u", {})
    assert out == {"ok": True}
    assert len(p._client.messages.calls) == 1, "repair path should not retry"


def test_anthropic_retries_once_on_malformed_then_succeeds() -> None:
    p = _anthropic(["not json at all", '{"ok": true}'])
    out = p.complete_json("s", "u", {})
    assert out == {"ok": True}
    assert len(p._client.messages.calls) == 2


def test_anthropic_raises_after_two_invalid_responses() -> None:
    p = _anthropic(["garbage one", "garbage two"])
    with pytest.raises(ValueError, match="invalid JSON twice"):
        p.complete_json("s", "u", {})
    assert len(p._client.messages.calls) == 2


def test_anthropic_rewrite_returns_concatenated_text() -> None:
    p = _anthropic(["Острее: текст готов."])
    out = p.rewrite("Исходный текст.", mode="sharper")
    assert out == "Острее: текст готов."


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class _OMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _OChoice:
    def __init__(self, content: str) -> None:
        self.message = _OMessage(content)


class _OResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_OChoice(content)]


class _OCompletions:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kw):
        self.calls.append(kw)
        if not self._responses:
            raise AssertionError("provider called create() more times than mocked responses")
        return _OResponse(self._responses.pop(0))


class _OChat:
    def __init__(self, responses: list[str]) -> None:
        self.completions = _OCompletions(responses)


class _OClient:
    def __init__(self, responses: list[str]) -> None:
        self.chat = _OChat(responses)


def _openai(responses: list[str]) -> OpenAIProvider:
    p = OpenAIProvider("sk-placeholder", model="gpt-test")
    p._client = _OClient(responses)
    return p


def test_openai_complete_json_returns_parsed_dict() -> None:
    p = _openai(['{"ok": true, "topic": "y"}'])
    out = p.complete_json("sys", "тема: y", {"type": "object"})
    assert out == {"ok": True, "topic": "y"}


def test_openai_uses_json_object_response_format() -> None:
    p = _openai(['{"ok": true}'])
    p.complete_json("sys", "u", {})
    sent = p.chat_calls()[0] if hasattr(p, "chat_calls") else p._client.chat.completions.calls[0]
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["model"] == "gpt-test"


def test_openai_retries_once_on_malformed_then_succeeds() -> None:
    p = _openai(["lalala", '{"ok": true}'])
    out = p.complete_json("s", "u", {})
    assert out == {"ok": True}
    assert len(p._client.chat.completions.calls) == 2


def test_openai_raises_after_two_invalid_responses() -> None:
    p = _openai(["a", "b"])
    with pytest.raises(ValueError, match="invalid JSON twice"):
        p.complete_json("s", "u", {})


def test_openai_rewrite_strips_whitespace() -> None:
    p = _openai(["  Rewritten text.\n"])
    assert p.rewrite("Original.", "sharper") == "Rewritten text."
