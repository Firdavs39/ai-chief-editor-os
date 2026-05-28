from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Base class for LLM provider adapters.

    Phase 6 added token telemetry: after every `complete_json` call,
    providers SHOULD update `last_input_tokens`, `last_output_tokens`, and
    `last_model` on `self`. The workflow reads these and persists them into
    `GenerationStep.tokens_in/out` so cost can be computed without storing
    raw prompts/responses.

    Providers that cannot report usage (mock, providers behind a thin proxy)
    leave the values as None — the workflow treats None as "not recorded".
    """

    name: str = "base"

    def __init__(self) -> None:
        # Phase 6: usage counters updated by subclasses after each call.
        self.last_input_tokens: int | None = None
        self.last_output_tokens: int | None = None
        self.last_model: str | None = None

    @abstractmethod
    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        temperature: float = 0.7,
    ) -> dict[str, Any]: ...

    @abstractmethod
    def rewrite(self, text: str, mode: str) -> str: ...

    def _safe_parse(self, raw: str) -> dict[str, Any] | None:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    return None
            return None

    def _record_usage(
        self,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        model: str | None = None,
    ) -> None:
        """Subclasses call this after each LLM round-trip. Adding accumulates
        across the call cycle when a provider does its own internal retry."""
        if input_tokens is not None:
            self.last_input_tokens = (self.last_input_tokens or 0) + int(input_tokens)
        if output_tokens is not None:
            self.last_output_tokens = (self.last_output_tokens or 0) + int(output_tokens)
        if model is not None:
            self.last_model = model

    def _reset_usage(self) -> None:
        """Reset counters at the START of `complete_json` so each public
        call returns fresh totals."""
        self.last_input_tokens = None
        self.last_output_tokens = None
        # Note: last_model is intentionally NOT reset — it's a static fact
        # about the configured provider.
