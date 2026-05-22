"""Per-step system + user prompts and JSON schemas for the Quality
Editorial Workflow.

Design rules (per QUALITY_EDITORIAL_WORKFLOW_PLAN.md §9):

- Russian-first system prompts. UI labels stay English; generated content
  is Russian by default.
- Every prompt ends with the mandatory safety footer:
    "Do not invent facts. Do not publish. Do not approve."
- Every schema has ≤ 6 fields where practical. The Editor-in-Chief Draft
  step is the documented exception at 9 fields because it assembles, not
  generates.
- `editorial_rationale` appears FIRST when a short user-safe explanation is
  needed (≤ 1500 chars, safe to render in UI; NOT private chain-of-thought).
  Phase 5.2 raised this cap from 240 because Kimi K2.6 wrote honest
  multi-sentence rationales that legitimately exceeded the old limit.
- Content-field maxLength values mirror real per-platform API limits
  (TG=4096, Threads=500, Reddit body=10000, Reddit title=300). The schema
  must NOT be more generous than the platform itself.
- Prompts never reference secrets, env-var names, the Vault, or any
  publishing surface.
"""

from __future__ import annotations

from typing import Any

from ...models import RawItem, StyleProfile, TrendCluster

SAFETY_FOOTER = "Do not invent facts. Do not publish. Do not approve."

_RU_LANG = "ru-RU"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _trim(text: str, n: int) -> str:
    text = (text or "").strip()
    return text[: n - 1] + "…" if len(text) > n else text


def _format_style(style: StyleProfile | None) -> str:
    if style is None:
        return (
            "Tone: экспертный, плотный; Audience: контент-маркетологи и редакторы; "
            "Language: ru-RU; Writing rules: краткость, конкретика, факты, "
            "без штампов."
        )
    banned = ", ".join((style.banned_phrases or [])[:10])
    examples = "\n---\n".join((style.example_posts or [])[:2])
    return (
        f"Tone: {style.tone}. Audience: {style.audience}. "
        f"Language: {style.lang_primary or _RU_LANG}. "
        f"Writing rules: {style.writing_rules}. "
        f"Banned phrases (avoid): {banned}.\n"
        f"Voice examples:\n{examples}"
    )


def _format_cluster_context(
    cluster: TrendCluster | None, raw_items: list[RawItem]
) -> str:
    if cluster is None:
        return "Кластер не указан."
    keywords = ", ".join((cluster.keywords or [])[:8])
    score = cluster.score_breakdown or {}
    body = "\n\n".join(
        f"{(r.title or '').strip()}\n{(r.body or '').strip()}".strip() for r in raw_items
    )
    return (
        f"Тема кластера: {cluster.representative_text[:200]}\n"
        f"Keywords: {keywords}\n"
        f"Score breakdown: {score}\n"
        f"Источники:\n{_trim(body, 1800)}"
    )


def _editorial_role_preamble(role_ru: str) -> str:
    return (
        f"Ты — {role_ru} в редакции AI Chief Editor OS. "
        f"Пишешь по-русски. Возвращаешь строго JSON по указанной схеме."
    )


def _safety_block() -> str:
    return f"\n\n{SAFETY_FOOTER}"


# ---------------------------------------------------------------------------
# JSON schemas — flat, ≤ 6 fields, editorial_rationale first when used.
# ---------------------------------------------------------------------------


SCHEMA_RESEARCH_BRIEF: dict[str, Any] = {
    "type": "object",
    "required": [
        "editorial_rationale",
        "fact_bullets",
        "source_handles",
        "gaps",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "fact_bullets": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 7,
        },
        "source_handles": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "gaps": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
    },
}

SCHEMA_ANGLE: dict[str, Any] = {
    "type": "object",
    "required": [
        "editorial_rationale",
        "primary_angle",
        "contrarian_take",
        "why_now",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "primary_angle": {"type": "string"},
        "contrarian_take": {"type": "string"},
        "why_now": {"type": "string"},
    },
}

SCHEMA_PSYCH: dict[str, Any] = {
    "type": "object",
    "required": [
        "editorial_rationale",
        "target_emotion",
        "hook_pattern",
        "cognitive_bias_lever",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "target_emotion": {"type": "string"},
        "hook_pattern": {"type": "string"},
        "cognitive_bias_lever": {"type": "string"},
    },
}

SCHEMA_VOICE_BRIEF: dict[str, Any] = {
    "type": "object",
    "required": [
        "editorial_rationale",
        "sentence_length_target",
        "vocab_lane",
        "must_avoid",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "sentence_length_target": {"type": "string"},
        "vocab_lane": {"type": "string"},
        "must_avoid": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
    },
}

SCHEMA_TG_POST: dict[str, Any] = {
    "type": "object",
    "required": ["editorial_rationale", "body", "hook", "cta"],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "body": {"type": "string", "maxLength": 4096},
        "hook": {"type": "string", "maxLength": 160},
        "cta": {"type": "string"},
    },
}

SCHEMA_THREADS_POST: dict[str, Any] = {
    "type": "object",
    "required": ["editorial_rationale", "body", "cta"],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "body": {"type": "string", "maxLength": 500},
        "cta": {"type": "string"},
    },
}

SCHEMA_REDDIT_POST: dict[str, Any] = {
    "type": "object",
    "required": ["editorial_rationale", "title", "body", "cta"],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "title": {"type": "string", "maxLength": 300},
        "body": {"type": "string", "maxLength": 10000},
        "cta": {"type": "string"},
    },
}

SCHEMA_CRITIC_REPORT: dict[str, Any] = {
    "type": "object",
    "required": [
        "editorial_rationale",
        "slop_count",
        "factual_concerns",
        "length_issues",
        "hook_grade",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "slop_count": {"type": "integer", "minimum": 0},
        "factual_concerns": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "length_issues": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "hook_grade": {"type": "integer", "minimum": 0, "maximum": 10},
    },
}

# Editor-in-Chief Draft — documented exception at 9 fields because it
# ASSEMBLES (selects and lightly polishes), not generates new content.
SCHEMA_FINAL_BRIEF: dict[str, Any] = {
    "type": "object",
    "required": [
        "editorial_rationale",
        "topic",
        "source_summary",
        "why_it_matters",
        "psychology_hook",
        "final_tg",
        "final_threads",
        "final_reddit",
        "cta",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "topic": {"type": "string"},
        "source_summary": {"type": "string", "maxLength": 2000},
        "why_it_matters": {"type": "string", "maxLength": 1500},
        "psychology_hook": {"type": "string", "maxLength": 1500},
        "final_tg": {"type": "string", "maxLength": 4096},
        "final_threads": {"type": "string", "maxLength": 500},
        "final_reddit": {"type": "string", "maxLength": 10000},
        "cta": {"type": "string"},
    },
}

SCHEMA_QUALITY_REPORT: dict[str, Any] = {
    "type": "object",
    "required": [
        "editorial_rationale",
        "style_match_score",
        "viral_score",
        "slop_risk",
        "controversy_risk",
        "recommendation",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "style_match_score": {"type": "number", "minimum": 0, "maximum": 1},
        "viral_score": {"type": "number", "minimum": 0, "maximum": 1},
        "slop_risk": {"type": "number", "minimum": 0, "maximum": 1},
        "controversy_risk": {"type": "number", "minimum": 0, "maximum": 1},
        "recommendation": {
            "type": "string",
            "enum": ["approve", "revise", "reject"],
        },
    },
}


# ---------------------------------------------------------------------------
# System prompts (Russian + safety footer)
# ---------------------------------------------------------------------------


_RATIONALE_RULE = (
    "Поле editorial_rationale — короткий публичный editorial summary "
    "(≤1500 символов, обычно 200–800). Это объяснение твоего выбора для "
    "редактора, безопасное для показа в UI. НЕ chain-of-thought, не пересказ "
    "контента, не служебные размышления."
)


def system_research_analyst(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("главный аналитик-исследователь")
        + " Анализируешь сигналы из источников, выделяешь факты, источники и пробелы. "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_trend_strategist(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("стратег по трендам")
        + " На основе фактов формулируешь основной угол, контр-тейк и причину «почему сейчас». "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_audience_psychology(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("аналитик психологии аудитории")
        + " Выявляешь целевую эмоцию, паттерн крючка и когнитивный «рычаг». "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_style_dna_editor(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("редактор Style DNA")
        + " Переводишь психологические рекомендации в правила голоса: целевая длина "
        "предложений, словарная полоса, чего избегать. "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_platform_writer_telegram(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("райтер для Telegram")
        + " Пишешь пост: технический лимит Telegram Bot API — 4096 символов, "
        "но стремись к плотным 600–1500 символам (короче работает лучше). "
        "Сильный крючок в первых 160 символах, конкретный CTA. "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_platform_writer_threads(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("райтер для Threads")
        + " Жёсткий лимит платформы Threads — 500 символов. Короткий ёмкий пост с CTA. "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_platform_writer_reddit(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("райтер для Reddit")
        + " Заголовок до 300 символов (лимит Reddit), тело до 10000 (soft cap; "
        "обычно лучше 800–3000). Можешь писать по-русски или по-английски — следуй "
        "языку источника. "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_critic_red_team(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("критик / red team")
        + " Проверяешь черновики на штампы (slop), фактические сомнения, проблемы "
        "длины и силу крючка (0-10). "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_editor_in_chief_draft(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("главный редактор (Editor-in-Chief)")
        + " Собираешь финальный brief: подбираешь лучшие версии Telegram/Threads/Reddit, "
        "формулируешь topic / source_summary / why_it_matters / psychology_hook / cta. "
        "Не публикуешь и не одобряешь — ты только собираешь. "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_quality_judge(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("Quality Judge")
        + " Оцениваешь финальный brief по четырём метрикам (0..1): style_match_score, "
        "viral_score, slop_risk, controversy_risk. Выдаёшь recommendation: "
        "approve | revise | reject. Эта recommendation — это рекомендация редактору, "
        "а не реальное одобрение в продукте. "
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


# ---------------------------------------------------------------------------
# User-prompt builders. Each takes the run context + prior artifacts dict.
# Artifacts are addressed by their canonical name (see services/generation/steps.py).
# ---------------------------------------------------------------------------


def user_research_analyst(
    cluster: TrendCluster | None, raw_items: list[RawItem]
) -> str:
    return (
        _format_cluster_context(cluster, raw_items)
        + "\n\nВерни JSON с полями: editorial_rationale, fact_bullets (3-7), "
        "source_handles (≤5), gaps (≤3). "
        + SAFETY_FOOTER
    )


def user_trend_strategist(
    cluster: TrendCluster | None, artifacts: dict
) -> str:
    rb = artifacts.get("research_brief", {})
    score = (cluster.score_breakdown if cluster else {}) or {}
    return (
        f"Research brief:\n{rb}\n"
        f"Score breakdown: {score}\n\n"
        "Сформируй: primary_angle (основной угол), contrarian_take (контр-тейк, "
        "если уместен), why_now (почему сейчас). editorial_rationale ≤ 1500 симв. "
        + SAFETY_FOOTER
    )


def user_audience_psychology(artifacts: dict, style: StyleProfile | None) -> str:
    angle = artifacts.get("angle", {})
    audience = (style.audience if style else "контент-маркетологи и редакторы") or ""
    return (
        f"Angle: {angle}\nAudience: {audience}\n\n"
        "Определи target_emotion, hook_pattern, cognitive_bias_lever. "
        "editorial_rationale ≤ 1500. " + SAFETY_FOOTER
    )


def user_style_dna_editor(artifacts: dict, style: StyleProfile | None) -> str:
    psych = artifacts.get("psych", {})
    return (
        f"Psych brief: {psych}\nStyle: {_format_style(style)}\n\n"
        "Дай: sentence_length_target (например, «короткие, 8-14 слов»), "
        "vocab_lane («экспертный, без жаргона»), must_avoid (≤5). "
        "editorial_rationale ≤ 1500. " + SAFETY_FOOTER
    )


def user_platform_writer(artifacts: dict, platform: str, *, style: StyleProfile | None) -> str:
    voice = artifacts.get("voice_brief", {})
    angle = artifacts.get("angle", {})
    return (
        f"Voice brief: {voice}\nAngle: {angle}\nStyle: {_format_style(style)}\n\n"
        f"Напиши {platform}-версию. Соблюдай длину под платформу. "
        "Поля JSON: editorial_rationale + (body / hook / cta или title / body / cta). "
        + SAFETY_FOOTER
    )


def user_critic_red_team(artifacts: dict) -> str:
    tg = artifacts.get("tg_post", {})
    th = artifacts.get("threads_post", {})
    rd = artifacts.get("reddit_post", {})
    return (
        f"Telegram: {tg}\nThreads: {th}\nReddit: {rd}\n\n"
        "Прогон red-team: slop_count (число штампов), factual_concerns (≤3 "
        "пункта), length_issues (≤3), hook_grade (0-10). "
        "editorial_rationale ≤ 1500. " + SAFETY_FOOTER
    )


def user_editor_in_chief_draft(artifacts: dict) -> str:
    rb = artifacts.get("research_brief", {})
    angle = artifacts.get("angle", {})
    psych = artifacts.get("psych", {})
    tg = artifacts.get("tg_post", {})
    th = artifacts.get("threads_post", {})
    rd = artifacts.get("reddit_post", {})
    critic = artifacts.get("critic_report", {})
    return (
        f"Research: {rb}\nAngle: {angle}\nPsych: {psych}\n"
        f"Telegram draft: {tg}\nThreads draft: {th}\nReddit draft: {rd}\n"
        f"Critic report: {critic}\n\n"
        "Собери final_brief: topic, source_summary (≤2000), why_it_matters (≤1500), "
        "psychology_hook (≤1500), final_tg (≤4096, цель 600–1500), "
        "final_threads (≤500), final_reddit (≤10000, цель 800–3000), cta. "
        "Учти замечания критика. editorial_rationale ≤ 1500. " + SAFETY_FOOTER
    )


def user_quality_judge(artifacts: dict) -> str:
    fb = artifacts.get("final_brief", {})
    critic = artifacts.get("critic_report", {})
    return (
        f"Final brief: {fb}\nCritic report: {critic}\n\n"
        "Оцени: style_match_score, viral_score, slop_risk, controversy_risk "
        "(все в [0, 1]), recommendation ∈ {approve, revise, reject}. "
        "Помни: recommendation — это рекомендация редактору, НЕ автоматическое "
        "одобрение в продукте. editorial_rationale ≤ 1500. " + SAFETY_FOOTER
    )


__all__ = [
    "SAFETY_FOOTER",
    "SCHEMA_ANGLE",
    "SCHEMA_CRITIC_REPORT",
    "SCHEMA_FINAL_BRIEF",
    "SCHEMA_PSYCH",
    "SCHEMA_QUALITY_REPORT",
    "SCHEMA_REDDIT_POST",
    "SCHEMA_RESEARCH_BRIEF",
    "SCHEMA_TG_POST",
    "SCHEMA_THREADS_POST",
    "SCHEMA_VOICE_BRIEF",
    "system_audience_psychology",
    "system_critic_red_team",
    "system_editor_in_chief_draft",
    "system_platform_writer_reddit",
    "system_platform_writer_telegram",
    "system_platform_writer_threads",
    "system_quality_judge",
    "system_research_analyst",
    "system_style_dna_editor",
    "system_trend_strategist",
    "user_audience_psychology",
    "user_critic_red_team",
    "user_editor_in_chief_draft",
    "user_platform_writer",
    "user_quality_judge",
    "user_research_analyst",
    "user_style_dna_editor",
    "user_trend_strategist",
]
