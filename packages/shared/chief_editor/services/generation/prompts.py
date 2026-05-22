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
from .editorial_rules import (
    ALL_BANNED_TELLS,
    CTA_GUIDANCE,
    DEAD_LEVERS,
    EMOTION_TAXONOMY,
    EVASION_RULES,
    HOOK_PATTERNS,
)

SAFETY_FOOTER = "Do not invent facts. Do not publish. Do not approve."

_RU_LANG = "ru-RU"


def _format_emotion_taxonomy() -> str:
    """Compact Russian-language list of allowed emotion_target values."""
    lines = []
    for key, val in EMOTION_TAXONOMY.items():
        lines.append(f"- {key} ({val['ru_name']}): {val['when']}")
    return "\n".join(lines)


def _format_hook_patterns() -> str:
    """Compact Russian-language list of named hook patterns with one example each."""
    lines = []
    for key, val in HOOK_PATTERNS.items():
        ex = val["examples"][0] if isinstance(val.get("examples"), tuple) else ""
        lines.append(f"- {key} ({val['ru_name']}): {val['skeleton']} Пример: «{ex}»")
    return "\n".join(lines)


def _format_evasion_rules() -> str:
    """The 10 numbered writer-evasion rules from research."""
    return "\n".join(f"{i+1}. {r}" for i, r in enumerate(EVASION_RULES))


def _format_banned_tells_compact() -> str:
    """Top 30 banned phrases as a single comma-quoted list (token-efficient)."""
    top = ALL_BANNED_TELLS[:30]
    return ", ".join(f"«{p}»" for p in top)


# Module-level pre-formatted strings — built once, reused across every
# prompt call. Saves tokens vs rebuilding per request.
_EMOTION_TAXONOMY_TEXT = _format_emotion_taxonomy()
_HOOK_PATTERNS_TEXT = _format_hook_patterns()
_EVASION_RULES_TEXT = _format_evasion_rules()
_BANNED_TELLS_TEXT = _format_banned_tells_compact()
_DEAD_LEVERS_TEXT = ", ".join(DEAD_LEVERS)


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
    """Phase Q: emit specific 2026-current emotion + recognition moment +
    sharp lever description. The 'cognitive_bias_lever' string field MUST
    follow format «<bias> via <mechanism> at <click_position>» (≤25 слов)."""
    return (
        _editorial_role_preamble("аналитик психологии аудитории")
        + " Твоя задача в 2026: НЕ инъекция biases в читателя, а НАЗЫВАНИЕ "
        "недовысказанной мысли, которая у читателя уже есть. Цель — узнавание, "
        "не убеждение. "
        "\n\nПоле target_emotion ОБЯЗАНО быть одним из 15 значений из таксономии "
        "ниже (ключ snake_case, не свободный текст):\n"
        + _EMOTION_TAXONOMY_TEXT
        + "\n\nПоле hook_pattern ОБЯЗАНО быть одним из 8 паттернов:\n"
        + _HOOK_PATTERNS_TEXT
        + "\n\nПоле cognitive_bias_lever ОБЯЗАНО следовать формату:\n"
        "«<bias> via <mechanism> at <click_position>» (≤25 слов).\n"
        "Хороший пример: «anchoring via contrast at line 1 — stat sets baseline, "
        "line 2 reframes felt meaning».\n"
        "ЗАПРЕЩЕНО выдавать «выгоревшие» рычаги: " + _DEAD_LEVERS_TEXT + ". "
        "Если рассмотрел один из них — переформулируй через actual recognition.\n"
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
        _editorial_role_preamble("райтер для Telegram (RU professional, май 2026)")
        + " Лимит Bot API — 4096; engagement-оптимальная длина 800-1500. Лучше короче.\n\n"
        "ПРАВИЛА (10 имп­ера­тивов, обязательны):\n"
        + _EVASION_RULES_TEXT
        + "\n\nХУКИ — выбери ОДИН из 8 паттернов, не смешивай:\n"
        + _HOOK_PATTERNS_TEXT
        + "\n\nЗАПРЕЩЁННЫЕ ФРАЗЫ (если встретил — переписать): "
        + _BANNED_TELLS_TEXT
        + "...\n\n"
        + CTA_GUIDANCE
        + "\n\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_platform_writer_threads(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("райтер для Threads (RU professional)")
        + " Жёсткий лимит платформы 500 символов. Engagement-оптимально 180-380. "
        "Заканчивай открытым вопросом — алгоритм Threads оптимизирует под "
        "reply-chain depth, не лайки.\n\n"
        "ПРАВИЛА (применить адаптированно под формат): "
        "open с конкретной деталью (имя/число/сцена); ОДНО короткое предложение "
        "под 6 слов; ОДНО длинное под 25 слов; минимум одна локатируемая "
        "конкретика; в конце — открытый вопрос конкретному читателю.\n\n"
        "ЗАПРЕЩЕНО: " + _BANNED_TELLS_TEXT + ".\n\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_platform_writer_reddit(style: StyleProfile | None) -> str:
    return (
        _editorial_role_preamble("райтер для Reddit (RU + EN ready)")
        + " Лимит title 300, лимит body 10000. Engagement-оптимально: "
        "title 60-90 символов (полное утверждение или вопрос, без clickbait — "
        "сообщество жёстко минусует); body 800-2000. "
        "TL;DR в конце, не в начале (RU-конвенция 2026).\n\n"
        "Можешь писать по-русски или по-английски — следуй языку источника.\n\n"
        "ПРАВИЛА (10 импе­ра­тивов адаптированно):\n"
        + _EVASION_RULES_TEXT
        + "\n\nЗАПРЕЩЕНО: " + _BANNED_TELLS_TEXT + ".\n\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_critic_red_team(style: StyleProfile | None) -> str:
    """Phase Q: critic now receives deterministic AI-tells flags from the
    Python detector AND adds its own editorial judgement on top."""
    return (
        _editorial_role_preamble("критик / red team (RU editorial 2026)")
        + " Проверяешь три черновика (TG / Threads / Reddit) на:\n"
        "1. Слабый крючок — первые 1-2 строки должны останавливать скролл.\n"
        "2. Несовпадение emotion_target и текста (если psych сказал «validated_cynicism», "
        "а текст звучит как cheerleading — это hard fail).\n"
        "3. Отсутствие конкретного якоря (имя, дата, цифра с дробью, URL).\n"
        "4. Wrap-up концовка («таким образом», «подводя итог» — флаг).\n"
        "5. Симметричные тройки «X, Y и Z» — флаг.\n"
        "6. Em-dash flood (>2 тире в одном предложении).\n"
        "7. Mismatch языка/тона с целевой аудиторией.\n\n"
        "Дополнительно: в user-промпте ты получишь deterministic_flags — "
        "список механических AI-tells, обнаруженных Python-детектором. "
        "Эти флаги ОБЯЗАНЫ попасть в length_issues или factual_concerns и "
        "увеличить slop_count.\n\n"
        "ЗАПРЕЩЁННЫЕ ФРАЗЫ в драфтах (если найдёшь — флагнуть): "
        + _BANNED_TELLS_TEXT
        + "...\n\nhook_grade 0-10: 0-3 = серый, 4-6 = средний, 7-8 = сильный, "
        "9-10 = выдающийся.\n"
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
    """Phase Q: calibrated score thresholds. Drafts with deterministic AI-tells
    flagged by the critic step cannot score >0.7 viral_score regardless of
    editorial polish — the floor checks ARE the floor."""
    return (
        _editorial_role_preamble("Quality Judge (RU editorial 2026)")
        + " Оцениваешь финальный brief по четырём метрикам (0..1) и выдаёшь "
        "recommendation: approve | revise | reject.\n\n"
        "КАЛИБРОВКА score-ов:\n"
        "- style_match_score: 0.0 = чужой голос, 0.5 = generic SMM, "
        "0.7 = соответствует Style DNA, 0.9 = воспроизводит фирменный приём.\n"
        "- viral_score: 0.0 = пройдут мимо, 0.5 = прочитают и забудут, "
        "0.7 = сохранят, 0.85+ = перешлют (требует крючка из 8 паттернов И "
        "конкретного якоря).\n"
        "- slop_risk: 0.0 = читается как человек, 0.3 = есть лёгкие AI-следы, "
        "0.5 = заметные штампы, 0.8+ = очевидно AI. ОБЯЗАТЕЛЬНО учитывай "
        "deterministic_flags из critic_report.\n"
        "- controversy_risk: 0.0 = безопасно, 0.5 = вызовет диалог, "
        "0.8+ = риск репутации.\n\n"
        "Recommendation logic:\n"
        "- approve: viral≥0.75 И slop_risk≤0.30 И controversy_risk≤0.55\n"
        "- revise: иначе, если slop_risk≤0.50 (исправимо)\n"
        "- reject: slop_risk>0.50 ИЛИ controversy_risk>0.75\n\n"
        "Эта recommendation — рекомендация редактору, не автоматическое "
        "одобрение в продукте.\n"
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
    """Phase Q: prepends deterministic AI-tells flags to the critic's user
    prompt so the LLM critic can see what Python already caught."""
    from .ai_tells import analyze_drafts

    tg = artifacts.get("tg_post", {})
    th = artifacts.get("threads_post", {})
    rd = artifacts.get("reddit_post", {})

    # Deterministic floor checks — these MUST land in slop_count / length_issues
    # because they're already proven by Python.
    tells = analyze_drafts(
        tg_body=str(tg.get("body", "")),
        threads_body=str(th.get("body", "")),
        reddit_body=str(rd.get("body", "")),
    )
    flag_lines = []
    for platform, report in tells.items():
        if report.flags:
            for flag in report.flags:
                flag_lines.append(f"  [{platform}] {flag}")
    deterministic_block = (
        "DETERMINISTIC FLAGS (auto-detected, MUST surface in critic_report):\n"
        + ("\n".join(flag_lines) if flag_lines else "  (none — floor checks passed)")
    )

    return (
        f"Telegram: {tg}\nThreads: {th}\nReddit: {rd}\n\n"
        + deterministic_block
        + "\n\nПрогон red-team: slop_count (число штампов + deterministic flags), "
        "factual_concerns (≤3), length_issues (≤3 — включая deterministic), "
        "hook_grade (0-10). Если deterministic flags не пусты — slop_count "
        "ОБЯЗАН быть ≥ числу флагов. editorial_rationale ≤ 1500. "
        + SAFETY_FOOTER
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
