"""Critic agent — runs after candidate generation. Heuristic, deterministic."""

from __future__ import annotations

import re
from typing import Any

from .dedup import jaccard, tokens

_RU_SLOP_PATTERNS = [
    r"\bв эпоху\b",
    r"\bв современном мире\b",
    r"\bдавайте погрузимся\b",
    r"\bв этой статье\b",
    r"\bстоит отметить\b",
    r"\bне секрет, что\b",
    r"\bкак известно\b",
    r"\bв мире, где\b",
    r"\bв нашем быстро меняющемся мире\b",
]
_GENERIC_PATTERNS = [
    r"\bочень важно\b",
    r"\bсегодня все говорят\b",
    r"\bлюбой может\b",
]
_HEDGE_WORDS = {
    "возможно", "вероятно", "кажется", "может быть", "наверное", "якобы",
    "perhaps", "maybe", "possibly", "allegedly",
}
_IMPERATIVE_HINTS = {
    "сохрани", "подпишись", "перешли", "напиши", "поделись", "попробуй",
    "comment", "share", "save", "follow", "try",
}


def _hits(patterns: list[str], text: str) -> int:
    norm = text.lower()
    return sum(1 for p in patterns if re.search(p, norm))


def _ngram_diversity(text: str, n: int = 3) -> float:
    words = re.findall(r"[A-Za-zА-Яа-яЁё]+", text.lower())
    if len(words) < n:
        return 1.0
    grams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    if not grams:
        return 1.0
    return len(set(grams)) / len(grams)


def critique(
    *,
    tg_version: str,
    threads_version: str,
    cta: str,
    source_summary: str,
    psychology_hook: str,
    controversy_keywords_hits: int = 0,
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []

    if _hits(_RU_SLOP_PATTERNS, tg_version + " " + threads_version) >= 1:
        notes.append(
            {
                "check": "ai_slop",
                "severity": "high",
                "note": "Найдены ИИ-штампы — желательно удалить или переписать.",
            }
        )

    if _hits(_GENERIC_PATTERNS, tg_version) >= 1 or _ngram_diversity(tg_version) < 0.6:
        notes.append(
            {
                "check": "too_generic",
                "severity": "medium",
                "note": "Текст звучит слишком общо. Добавьте конкретный пример или цифру.",
            }
        )

    source_tokens = tokens(source_summary)
    tg_tokens = tokens(tg_version)
    if source_tokens and tg_tokens and jaccard(source_tokens, tg_tokens) > 0.75:
        notes.append(
            {
                "check": "copied_wording",
                "severity": "high",
                "note": "Слишком близко к исходному тексту источника. Перефразируйте.",
            }
        )

    head = tg_version.strip()[:80].lower()
    if not head or not any(w in head for w in {"?", ":", "—", "никто", "тихая", "если", "что"}):
        notes.append(
            {
                "check": "weak_hook",
                "severity": "medium",
                "note": "Слабый крючок в первых 80 символах — усильте intro.",
            }
        )

    cta_words = set(re.findall(r"[A-Za-zА-Яа-яЁё]+", cta.lower()))
    if not cta_words & _IMPERATIVE_HINTS:
        notes.append(
            {
                "check": "weak_cta",
                "severity": "medium",
                "note": "В CTA нет повелительного действия. Скажите читателю, что именно сделать.",
            }
        )

    if len(tg_version) > 1024:
        notes.append(
            {
                "check": "length_issue",
                "severity": "high",
                "note": "Telegram-версия длиннее 1024 символов — сократите.",
            }
        )
    if len(threads_version) > 500:
        notes.append(
            {
                "check": "length_issue",
                "severity": "high",
                "note": "Threads-версия длиннее 500 символов — сократите.",
            }
        )

    if controversy_keywords_hits >= 2:
        notes.append(
            {
                "check": "controversy_risk",
                "severity": "high",
                "note": "Сильный спорный сигнал. Перепроверьте формулировки и факты.",
            }
        )

    hedge_count = sum(1 for w in _HEDGE_WORDS if w in tg_version.lower())
    if hedge_count >= 3:
        notes.append(
            {
                "check": "factual_uncertainty",
                "severity": "medium",
                "note": "Много hedge-слов («возможно», «кажется») — проверьте источник или уберите неуверенность.",
            }
        )

    return notes
