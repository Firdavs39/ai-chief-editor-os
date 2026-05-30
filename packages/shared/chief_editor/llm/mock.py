"""Deterministic mock LLM provider. Produces realistic Russian copy.

Used both as the default in MOCK_MODE and as a fallback when real keys are
missing. Output is deterministic given the same inputs (no randomness) so
tests can rely on it.
"""

from __future__ import annotations

import hashlib
import json
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

    def __init__(self) -> None:
        super().__init__()
        self.last_model = "mock"

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        # Mock telemetry: approximate tokens as char-count / 4 so the
        # cost-tracking surface has something to read in tests. Real
        # providers report exact counts.
        self._reset_usage()
        approx_in = (len(system) + len(user)) // 4
        # Phase 2 dispatch: detect the workflow step from the schema's
        # required-key signature and return a deterministic per-step payload.
        # Falls through to the legacy 13-field response when the schema does
        # not match any known step (preserves `/brief/generate` mock-mode
        # behavior and the existing test contract).
        step_response = self._step_response_for_schema(schema, user, system)
        if step_response is not None:
            approx_out = len(json.dumps(step_response, ensure_ascii=False)) // 4
            self._record_usage(
                input_tokens=approx_in, output_tokens=approx_out, model="mock"
            )
            return step_response

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
        approx_out = len(json.dumps(result, ensure_ascii=False)) // 4
        self._record_usage(
            input_tokens=approx_in, output_tokens=approx_out, model="mock"
        )
        return result

    # ------------------------------------------------------------------
    # Phase 2 — per-step deterministic responses.
    # Matching uses the schema's `required` keyset (a stable signature
    # across providers). All outputs are Russian-first and bounded.
    # ------------------------------------------------------------------

    def _step_response_for_schema(
        self,
        schema: dict[str, Any],
        user: str,
        system: str,
    ) -> dict[str, Any] | None:
        required = tuple(sorted(schema.get("required") or []))
        seed = _seed_for(user + system)
        topic = self._extract_topic(user)
        keywords = self._extract_keywords(user)
        kw_blob = ", ".join(keywords[:3]) if keywords else "AI и контент"

        # research_brief
        if required == ("editorial_rationale", "fact_bullets", "gaps", "source_handles"):
            return {
                "editorial_rationale": _shorten(
                    f"Сигнал по теме «{topic}» подтверждён в нескольких источниках.",
                    240,
                ),
                "fact_bullets": [
                    f"Тренд связан с {kw_blob}.",
                    f"Сигнал растёт по {len(keywords) or 3} источникам.",
                    "Аудитория реагирует выше среднего.",
                ],
                "source_handles": ["@source_a", "@source_b"][: max(1, len(keywords))],
                "gaps": ["нет численных данных", "не хватает мнения эксперта"],
            }
        # angle
        if required == (
            "contrarian_take",
            "editorial_rationale",
            "primary_angle",
            "why_now",
        ):
            return {
                "editorial_rationale": _shorten(
                    f"Сейчас рабочее окно для острого взгляда на {topic}.", 240
                ),
                "primary_angle": f"Главный угол: {topic} — что упускают эксперты.",
                "contrarian_take": "Контр-тейк: тренд не для всех, нужна ниша.",
                "why_now": "Почему сейчас: сигнал в нескольких независимых источниках.",
            }
        # psych
        if required == (
            "cognitive_bias_lever",
            "editorial_rationale",
            "hook_pattern",
            "target_emotion",
        ):
            return {
                "editorial_rationale": _shorten(
                    "Целимся в FOMO + любопытство профессионала.", 240
                ),
                "target_emotion": "конструктивное беспокойство",
                "hook_pattern": "никто не говорит / тихая революция",
                "cognitive_bias_lever": "social proof (несколько источников)",
            }
        # tg_post
        if required == ("body", "cta", "editorial_rationale", "hook"):
            hook = _pick(_HOOKS_RU, seed)
            why = _pick(_WHY_RU, seed >> 3)
            cta = _pick(_CTAS_RU, seed >> 5)
            body = (
                f"{hook} {topic}.\n\n"
                f"{why.capitalize()}. Это меняет правила игры для авторов в нише.\n\n"
                f"{cta}"
            )
            return {
                "editorial_rationale": _shorten(
                    "Сильный крючок в первых 80 символах, конкретный CTA.", 240
                ),
                "body": _shorten(body, 1024),
                "hook": _shorten(hook + " " + topic, 80),
                "cta": cta,
            }
        # threads_post
        if required == ("body", "cta", "editorial_rationale"):
            cta = _pick(_CTAS_RU, seed >> 5)
            body = (
                f"{_pick(_HOOKS_RU, seed).rstrip(' :,.—')} — {topic.lower()}. "
                "Кто заметил это у себя в ленте?"
            )
            return {
                "editorial_rationale": _shorten(
                    "Короткий пост под Threads с вопросом-крючком.", 240
                ),
                "body": _shorten(body, 500),
                "cta": cta,
            }
        # reddit_post
        if required == ("body", "cta", "editorial_rationale", "title"):
            why = _pick(_WHY_RU, seed >> 3)
            cta = _pick(_CTAS_RU, seed >> 5)
            return {
                "editorial_rationale": _shorten(
                    "Reddit-формат: заголовок-наблюдение + аналитический body.", 240
                ),
                "title": _shorten(f"Observation: {topic}", 300),
                "body": _shorten(
                    f"Across multiple sources the same signal is showing up — "
                    f"{kw_blob}. My take: {why}.",
                    1500,
                ),
                "cta": cta,
            }
        # critic_report
        if required == (
            "editorial_rationale",
            "factual_concerns",
            "hook_grade",
            "length_issues",
            "slop_count",
        ):
            return {
                "editorial_rationale": _shorten(
                    "Черновик чистый, фактических сомнений нет.", 240
                ),
                "slop_count": 0,
                "factual_concerns": [],
                "length_issues": [],
                "hook_grade": 8,
            }
        # final_brief (9 fields — documented exception)
        # sorted order: final_tg < final_threads lexically ("g" < "h").
        if required == (
            "cta",
            "editorial_rationale",
            "final_reddit",
            "final_tg",
            "final_threads",
            "psychology_hook",
            "source_summary",
            "topic",
            "why_it_matters",
        ):
            hook = _pick(_HOOKS_RU, seed)
            why = _pick(_WHY_RU, seed >> 3)
            cta = _pick(_CTAS_RU, seed >> 5)
            tg_body = _shorten(
                f"{hook} {topic}.\n\n{why.capitalize()}. Рабочее окно для авторов в нише.\n\n{cta}",
                1024,
            )
            threads_body = _shorten(
                f"{hook.rstrip(' :,.—')} — {topic.lower()}. Кто заметил это в ленте?",
                500,
            )
            reddit_body = _shorten(
                f"Observation: {topic}. {why.capitalize()}. Curious if anyone is seeing this.",
                1500,
            )
            return {
                "editorial_rationale": _shorten(
                    "Финальная сборка: голос ровный, длины в норме, CTA конкретный.",
                    240,
                ),
                "topic": topic,
                "source_summary": _shorten(
                    f"Сигнал по {topic} в нескольких источниках: {kw_blob}.", 400
                ),
                "why_it_matters": _shorten(why.capitalize() + ".", 300),
                "psychology_hook": _shorten(hook, 200),
                "final_tg": tg_body,
                "final_threads": threads_body,
                "final_reddit": reddit_body,
                "cta": cta,
            }
        # fact_check (information-asymmetric grounding pass)
        if required == (
            "editorial_rationale",
            "grounding_score",
            "unsupported_claims",
        ):
            return {
                "editorial_rationale": _shorten(
                    "Проверяемые claim'ы финала привязаны к источникам.", 240
                ),
                "unsupported_claims": [],
                "grounding_score": 0.95,
            }
        # quality_report (now includes hook_score)
        if required == (
            "controversy_risk",
            "editorial_rationale",
            "hook_score",
            "recommendation",
            "slop_risk",
            "style_match_score",
            "viral_score",
        ):
            viral = 0.45 + (seed % 40) / 100
            slop = max(0.05, 0.35 - (seed % 30) / 100)
            controversy = (seed % 25) / 100
            style_fit = 0.65 + (seed % 25) / 100
            hook = 0.6 + (seed % 30) / 100
            return {
                "editorial_rationale": _shorten(
                    "Оценка по метрикам в [0,1]; рекомендация для редактора.",
                    240,
                ),
                "style_match_score": round(min(0.95, style_fit), 2),
                "viral_score": round(min(0.92, viral), 2),
                "slop_risk": round(slop, 2),
                "controversy_risk": round(controversy, 2),
                "hook_score": round(min(0.95, hook), 2),
                "recommendation": "approve" if slop < 0.25 and viral > 0.5 else "revise",
            }
        return None

    def rewrite(self, text: str, mode: str) -> str:
        if mode == "shorter":
            return _shorten(text, max(80, int(len(text) * 0.6)))
        if mode == "deslop":
            return _de_slop(text)
        prefix = _REWRITE_PREFIX.get(mode, "")
        return prefix + text.strip()

    @staticmethod
    def _extract_topic(user_prompt: str) -> str:
        # Accept both "тема:" and "тема кластера:" headers — the Phase 2
        # workflow uses the latter in research_analyst.
        match = re.search(
            r"тема(?:\s+кластера)?[:\-]\s*(.+)",
            user_prompt,
            flags=re.IGNORECASE,
        )
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
