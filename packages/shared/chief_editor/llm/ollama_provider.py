"""Ollama / OpenAI-compatible provider.

Targets:
- Ollama Cloud (`https://ollama.com`) with an API key — e.g. Kimi K2.6 via
  `kimi-k2.6:cloud`.
- Local Ollama (`http://localhost:11434`) with no auth — uses the sentinel
  key `ollama` which the local server accepts.

Wire format is the OpenAI Chat Completions API surface. We use the official
`openai` Python SDK with a custom `base_url` so the same retry / parse logic
the OpenAI provider uses applies here too.

Streaming is **not** used (this stage only needs structured-JSON outputs).
Multimodal (image inputs) is not wired here either — the schema-driven
`complete_json` is the only entrypoint Kimi sees.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from .base import LLMProvider


def _normalize_base_url(base_url: str) -> str:
    """Ensure the URL ends with `/v1` (OpenAI-compat suffix) and has no trailing slash."""
    base = (base_url or "").rstrip("/")
    if not base:
        return ""
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def host_of(base_url: str) -> str:
    """Return only the host portion of a URL — safe to include in readiness output."""
    try:
        parsed = urlparse(base_url)
        return parsed.netloc or parsed.path
    except Exception:
        return ""


class OllamaProvider(LLMProvider):
    name = "ollama"

    # Phase 5.2 follow-up: tighten timeout / retry behavior for Ollama Cloud.
    # The OpenAI SDK defaults to a 600 s timeout × 2 retries = up to 1 800 s
    # of waiting before the call fails. Run #2 of the Phase 5.2 validation
    # hit exactly this ceiling on a slow step. We prefer to fail faster:
    #   per-call timeout: 900 s (15 min) — generous enough for Kimi's
    #     longest legitimate response (final_brief output ~6 K tokens
    #     observed at ~25 min, but the actual API call is usually well
    #     under 15 min; if it isn't, retry is what salvages it).
    #   max_retries: 1 — single retry on a 5xx / connection error.
    # Worst case = 1 800 s as before, but typically 900 s and operators see
    # the failure sooner.
    DEFAULT_TIMEOUT_SECONDS = 900.0
    DEFAULT_MAX_RETRIES = 1
    # Phase Q follow-up: cap output tokens so Kimi can't go verbose past
    # the schema's reach. Phase 7 ran ~7K tokens/step on average; Phase Q
    # ran ~14K tokens/step (2× verbose) and one step timed out at the
    # Reddit 10K-char artifact. 4096 tokens is ~12-16K Russian chars —
    # 2× headroom over the largest artifact (final_brief).
    DEFAULT_MAX_TOKENS = 4096

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "kimi-k2.6:cloud",
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        max_tokens: int | None = None,
    ) -> None:
        super().__init__()
        if not base_url:
            raise ValueError("OllamaProvider requires a base URL")
        if not api_key:
            # The caller (registry) should resolve a local default before we get
            # here. Refuse rather than silently sending an unauthenticated POST.
            raise ValueError(
                "OllamaProvider requires an API key (or use a local base URL "
                "with the documented `ollama` sentinel token)"
            )
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - dep installed in prod
            raise RuntimeError(
                "openai package is required for OllamaProvider"
            ) from exc

        self._client = OpenAI(
            base_url=_normalize_base_url(base_url),
            api_key=api_key,
            timeout=(
                timeout_seconds
                if timeout_seconds is not None
                else self.DEFAULT_TIMEOUT_SECONDS
            ),
            max_retries=(
                max_retries
                if max_retries is not None
                else self.DEFAULT_MAX_RETRIES
            ),
        )
        self._model = model
        self._raw_base_url = base_url
        self.last_model = model
        self._max_tokens = (
            max_tokens
            if max_tokens is not None
            else self.DEFAULT_MAX_TOKENS
        )

    # ------------------------------------------------------------------ JSON

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """Ask Kimi for one strict-JSON answer. Retry once on parse failure."""
        self._reset_usage()
        base_user = (
            f"{user}\n\n"
            f"Return STRICT JSON only, matching this schema:\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n"
            f"Respond with one valid JSON object only — no prose, no markdown fences."
        )

        def _call(extra: str = "") -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=temperature,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": base_user + extra},
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

        # Repair-prompt retry. We tell the model its previous output failed
        # to parse without quoting any of its actual text (which could be
        # very long or include partial keys we don't want to amplify).
        raw = _call(
            "\n\nYour previous response could not be parsed as JSON. "
            "Reply ONLY with a single valid JSON object now, no other text."
        )
        parsed = self._safe_parse(raw)
        if parsed is None:
            raise ValueError(
                "ollama provider returned invalid JSON twice "
                f"(model={self._model}, host={host_of(self._raw_base_url)})"
            )
        return parsed

    # ------------------------------------------------------------------ rewrite

    def rewrite(self, text: str, mode: str) -> str:
        instructions = {
            "sharper": "Сделай текст острее, без воды. Сохрани смысл и язык.",
            "expert": "Перепиши как эксперт с уверенным тоном. Сохрани язык.",
            "shorter": "Сократи примерно на 40%. Сохрани главное и язык.",
            "human": "Сделай более человечным, как переписка другу. Сохрани язык.",
            "deslop": "Убери канцелярит, ИИ-штампы и общие фразы. Сохрани язык и факты.",
        }.get(mode, "Перепиши, сохрани язык и ключевые факты.")

        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.6,
            max_tokens=self._max_tokens,
            messages=[
                {
                    "role": "system",
                    "content": "You rewrite content carefully without inventing facts.",
                },
                {
                    "role": "user",
                    "content": f"{instructions}\n\nТекст:\n{text}",
                },
            ],
        )
        return (response.choices[0].message.content or "").strip()
