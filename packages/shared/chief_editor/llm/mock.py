"""Deterministic mock LLM provider. Produces realistic Russian copy.

Used both as the default in MOCK_MODE and as a fallback when real keys are
missing. Output is deterministic given the same inputs (no randomness) so
tests can rely on it.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .base import LLMProvider

_HOOKS_RU = [
    "Никто не говорит об этом вслух, но",
    "Самое неудобное наблюдение недели:",
    "Если коротко, индустрия снова сделала разворот —",
    "Тихая революция, которую все пропустили:",
    "Это меняет правила игры для маленьких авторов:",
    "Закономерность, которую видно только если смотреть на цифры:",
]

_WHY_RU = [
    "тренд формируется на стыке внимания аудитории и нового инструмента",
    "появилась рабочая механика, которой ещё нет в массовых гайдах",
    "сообщество начало менять язык, и это всегда опережает изменение спроса",
    "крупные игроки тестируют формат, а нишевые авторы получают окно",
    "сигнал подтверждается в нескольких независимых источниках одновременно",
]

_CTAS_RU = [
    "Сохрани, если планируешь писать про это в ближайшие 7 дней.",
    "Перешли тому, кто всё ещё пишет в старом формате.",
    "Поделись в комментариях, видишь ли ты этот сдвиг в своей нише.",
    "Подпишись — разбираем такие тренды раньше, чем они станут шумом.",
    "Сохрани шаблон и попробуй адаптировать под свой контент завтра.",
]

_REWRITE_PREFIX = {
    "sharper": "Острее: ",
    "expert": "Экспертный угол: ",
    "shorter": "",
    "human": "По-человечески: ",
    "deslop": "",
}

_SLOP_PATTERNS = [
    r"в эпоху(?:\s+\w+)?",
    r"в современном мире",
    r"давайте погрузимся",
    r"в этой статье мы рассмотрим",
    r"стоит отметить, что",
    r"не секрет, что",
]


def _seed_for(text: str) -> int:
    return int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)


def _pick(seq: list[str], seed: int) -> str:
    return seq[seed % len(seq)]


def _shorten(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _de_slop(text: str) -> str:
    out = text
    for pattern in _SLOP_PATTERNS:
        out = re.sub(pattern, "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip(" ,.;—-")


class MockLLMProvider(LLMProvider):
    name = "mock"

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        seed = _seed_for(user + system)
        topic = self._extract_topic(user)
        keywords = self._extract_keywords(user)
        hook = _pick(_HOOKS_RU, seed)
        why = _pick(_WHY_RU, seed >> 3)
        cta = _pick(_CTAS_RU, seed >> 5)
        keywords_blob = ", ".join(keywords[:3]) if keywords else "AI и контент"

        source_summary = (
            f"За последние сутки {topic} появляется сразу в нескольких источниках. "
            f"Сигналы пересекаются по словам: {keywords_blob}. "
            "Авторы тестируют формат, аудитория откликается необычно высоко."
        )

        tg_body = (
            f"{hook} {topic}.\n\n"
            f"{source_summary}\n\n"
            f"Почему это важно: {why}. Если ты делаешь контент в этой нише, "
            "сейчас рабочее окно, чтобы зайти со своей точкой зрения, "
            "а не догонять тренд через неделю.\n\n"
            f"{cta}"
        )

        threads_body = (
            f"{hook.rstrip(' :,.—')} — {topic.lower()}. "
            f"{why.capitalize()}. "
            "Кто заметил это у себя в ленте?"
        )

        reddit_body = (
            f"Observation: {topic}.\n\n"
            f"Across multiple Russian-speaking and English-speaking sources, the same signal — "
            f"{keywords_blob} — is showing up in independent feeds. "
            f"My take: {why}. "
            "Curious if anyone else is seeing this trend confirmed by their own analytics."
        )

        viral = 0.45 + (seed % 40) / 100
        slop = max(0.05, 0.35 - (seed % 30) / 100)
        controversy = (seed % 25) / 100
        style_fit = 0.65 + (seed % 25) / 100

        result = {
            "topic": topic,
            "source_summary": source_summary,
            "why_it_matters": why.capitalize() + ".",
            "psychology_hook": hook,
            "tg_version": _shorten(tg_body, 1024),
            "threads_version": _shorten(threads_body, 500),
            "reddit_version": _shorten(reddit_body, 1500),
            "cta": cta,
            "style_match_score": round(min(0.95, style_fit), 2),
            "viral_score": round(min(0.92, viral), 2),
            "slop_risk": round(slop, 2),
            "controversy_risk": round(controversy, 2),
            "recommendation": (
                "approve" if slop < 0.25 and viral > 0.5 else "revise"
            ),
        }
        return result

    def rewrite(self, text: str, mode: str) -> str:
        if mode == "shorter":
            return _shorten(text, max(80, int(len(text) * 0.6)))
        if mode == "deslop":
            return _de_slop(text)
        prefix = _REWRITE_PREFIX.get(mode, "")
        return prefix + text.strip()

    @staticmethod
    def _extract_topic(user_prompt: str) -> str:
        match = re.search(r"тема[:\-]\s*(.+)", user_prompt, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().split("\n")[0][:140]
        first_line = user_prompt.strip().split("\n")[0]
        return first_line[:140] if first_line else "Новый тренд в контент-индустрии"

    @staticmethod
    def _extract_keywords(user_prompt: str) -> list[str]:
        match = re.search(r"keywords[:\-]\s*(.+)", user_prompt, flags=re.IGNORECASE)
        if match:
            raw = match.group(1).split("\n")[0]
            return [w.strip() for w in re.split(r"[,;]", raw) if w.strip()][:6]
        words = re.findall(r"[A-Za-zА-Яа-яЁё]{4,}", user_prompt)
        seen: list[str] = []
        for w in words:
            wl = w.lower()
            if wl not in seen:
                seen.append(wl)
            if len(seen) >= 6:
                break
        return seen
