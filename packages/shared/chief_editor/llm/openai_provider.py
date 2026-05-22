"""OpenAI provider with structured JSON output + one retry."""

from __future__ import annotations

import json
from typing import Any

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        super().__init__()
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("openai package is not installed") from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self.last_model = model

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        self._reset_usage()
        prompt = (
            f"{user}\n\nReturn STRICT JSON only, matching this schema:\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )

        def _call() -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            usage = getattr(response, "usage", None)
            self._record_usage(
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
                model=self._model,
            )
            return response.choices[0].message.content or ""

        raw = _call()
        parsed = self._safe_parse(raw)
        if parsed is not None:
            return parsed

        raw = _call()
        parsed = self._safe_parse(raw)
        if parsed is None:
            raise ValueError("openai provider returned invalid JSON twice")
        return parsed

    def rewrite(self, text: str, mode: str) -> str:
        instructions = {
            "sharper": "Make this text sharper, no fluff. Keep meaning and language.",
            "expert": "Rewrite with expert confident tone. Keep language.",
            "shorter": "Shorten by roughly 40%. Keep the core and language.",
            "human": "Make it more human, like a message to a friend. Keep language.",
            "deslop": "Strip filler, AI-clichés, generic phrasing. Keep language and facts.",
        }.get(mode, "Rewrite while preserving language and key facts.")

        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.6,
            messages=[
                {"role": "system", "content": "You rewrite content carefully without inventing facts."},
                {"role": "user", "content": f"{instructions}\n\nText:\n{text}"},
            ],
        )
        return (response.choices[0].message.content or "").strip()
