"""Anthropic Claude provider with strict JSON output + one retry."""

from __future__ import annotations

import json
from typing import Any

from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-opus-4-7") -> None:
        super().__init__()
        try:
            import anthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency installed in prod
            raise RuntimeError("anthropic package is not installed") from exc

        self._client = anthropic.Anthropic(api_key=api_key)
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
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=system,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            usage = getattr(response, "usage", None)
            self._record_usage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                model=self._model,
            )
            parts = []
            for block in response.content:
                text = getattr(block, "text", None)
                if text:
                    parts.append(text)
            return "".join(parts)

        raw = _call()
        parsed = self._safe_parse(raw)
        if parsed is not None:
            return parsed

        raw = _call()
        parsed = self._safe_parse(raw)
        if parsed is None:
            raise ValueError("anthropic provider returned invalid JSON twice")
        return parsed

    def rewrite(self, text: str, mode: str) -> str:
        instructions = {
            "sharper": "Сделай текст острее, без воды. Сохрани смысл и язык.",
            "expert": "Перепиши как эксперт с уверенным тоном. Сохрани язык.",
            "shorter": "Сократи примерно на 40%. Сохрани главное и язык.",
            "human": "Сделай более человечным, как переписка другу. Сохрани язык.",
            "deslop": "Убери канцелярит, ИИ-штампы и общие фразы. Сохрани язык и факты.",
        }.get(mode, "Перепиши, сохрани язык и ключевые факты.")

        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            temperature=0.6,
            system="You rewrite content carefully without inventing facts.",
            messages=[
                {
                    "role": "user",
                    "content": f"{instructions}\n\nТекст:\n{text}",
                }
            ],
        )
        parts = []
        for block in response.content:
            piece = getattr(block, "text", None)
            if piece:
                parts.append(piece)
        return "".join(parts).strip()
