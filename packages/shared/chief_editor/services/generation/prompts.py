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
    DEAD_LEVERS,
    EMOTION_TAXONOMY,
    EVASION_RULES,
    HOOK_PATTERNS,
)

SAFETY_FOOTER = "Do not invent facts. Do not publish. Do not approve."

# Phase Q v4 explicit termination signal — Kimi K2.6 drifts and "thinks
# out loud" by default; an explicit STOP halves runaway-verbose risk
# (per Anthropic context-engineering posts + Adam Holter's K2-thinking
# review, May 2026). Appended to every system prompt at the end.
_STOP_SIGNAL = (
    "\n\nВерни строго один JSON-объект по схеме и СТОП. "
    "Не пиши размышления, не комментируй, не добавляй пояснения после JSON."
)

_RU_LANG = "ru-RU"


def _format_emotion_taxonomy_compact() -> str:
    """Phase Q v4 trim: name only, NO per-emotion 'when'/'opener_example'.
    Kimi knows these patterns conceptually — we just need to constrain
    the field's vocabulary to the 15 canonical keys."""
    return ", ".join(EMOTION_TAXONOMY.keys())


def _format_hook_patterns_compact() -> str:
    """Phase Q v4 trim: name + 1-line skeleton, NO inline examples.
    Cuts ~60% of token weight while keeping pattern semantics. The
    model can derive examples from the name + skeleton."""
    lines = []
    for key, val in HOOK_PATTERNS.items():
        lines.append(f"- {key}: {val['skeleton']}")
    return "\n".join(lines)


def _format_evasion_rules() -> str:
    """The 10 numbered writer-evasion rules from research. KEPT in full —
    these are the core mechanical guidance and removing them degrades
    quality directly."""
    return "\n".join(f"{i+1}. {r}" for i, r in enumerate(EVASION_RULES))


# Module-level pre-formatted strings — built once, reused across every
# prompt call. Saves tokens vs rebuilding per request.
#
# Phase Q v4 (post-validation-failures): trimmed system prompts to free
# Kimi from "instruction-stacking paralysis". The 51-phrase banned-tells
# list is NOT injected into the prompt anymore — the deterministic
# detector in ai_tells.py catches them post-generation regardless.
_EMOTION_TAXONOMY_TEXT = _format_emotion_taxonomy_compact()
_HOOK_PATTERNS_TEXT = _format_hook_patterns_compact()
_EVASION_RULES_TEXT = _format_evasion_rules()
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
    return f"\n\n{SAFETY_FOOTER}{_STOP_SIGNAL}"


# ---------------------------------------------------------------------------
# Bulletproof prompt scaffolding (audit refactor, prompt-engineering-lead).
#
# Every system prompt follows the same section order:
#   MISSION → PERSONA (+ NEGATIVE SCOPE) → INPUTS (delimited) → OUTPUT →
#   HARD RULES (≤5) → BAD→GOOD → SAFETY+STOP.
# The helpers below assemble that skeleton so each role stays inside its
# token budget (writer 350-550, analytic/judge 200-350) and so the
# NEGATIVE SCOPE re-anchor is identical across roles.
# ---------------------------------------------------------------------------


def _negative_scope(role_ru: str, *, only: str) -> str:
    """PERSONA + NEGATIVE SCOPE line: who you are and what you must NOT do."""
    return (
        f"PERSONA: ты — {role_ru}. Ты только {only}. "
        "Не оценивай чужую работу, не переписывай за других, не публикуй и "
        "не одобряй — это делают другие роли."
    )


def wrap_input(tag: str, value: object) -> str:
    """Wrap a prompt input in XML-style delimiters so the model can tell
    instructions from data. Replaces the old bare f"{dict}" interpolation
    (a prompt-injection and role-confusion risk)."""
    return f"<{tag}>\n{value}\n</{tag}>"


def _role_reanchor(role_ru: str) -> str:
    """First line of every USER prompt — re-pins the role after the system
    prompt so long contexts don't let the model drift into another role."""
    return f"Действуй строго как {role_ru}.\n\n"


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

# Fact-checker — information-asymmetric grounding pass over the FINAL text.
SCHEMA_FACT_CHECK: dict[str, Any] = {
    "type": "object",
    "required": [
        "editorial_rationale",
        "unsupported_claims",
        "grounding_score",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "unsupported_claims": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "grounding_score": {"type": "number", "minimum": 0, "maximum": 1},
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
        "hook_score",
        "recommendation",
    ],
    "properties": {
        "editorial_rationale": {"type": "string", "maxLength": 1500},
        "style_match_score": {"type": "number", "minimum": 0, "maximum": 1},
        "viral_score": {"type": "number", "minimum": 0, "maximum": 1},
        "slop_risk": {"type": "number", "minimum": 0, "maximum": 1},
        "controversy_risk": {"type": "number", "minimum": 0, "maximum": 1},
        "hook_score": {"type": "number", "minimum": 0, "maximum": 1},
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

# Phase Q v7 — anti-example sketch for writer prompts (R3 finding: positive
# examples define center of target, negative examples define edges).
# ONE compact line per writer prompt — Anthropic skill-creator Bad/Good pattern.
# Sourced from R2's anti-example fingerprint (May 2026 verified).
_WRITER_ANTI_EXAMPLE = (
    "❌ Анти-пример (НЕ пиши так): «В современном мире AI меняет всё. "
    "Стоит отметить ключевую роль данных технологий. Подписывайтесь, "
    "чтобы не пропустить разбор!» — empty opening + АИ-штампы + generic "
    "anti-CTA. ✓ Пиши конкретику: имя/дата/цифра с дробью + одна "
    "screenshottable строка ≤60 символов + анти-CTA или открытый вопрос."
)


def system_research_analyst(style: StyleProfile | None) -> str:
    return (
        "MISSION: из сигналов источников выдать проверяемые факты, источники "
        "и пробелы для остальной редакции.\n"
        + _negative_scope("аналитик-исследователь", only="собираешь факты")
        + "\nINPUTS: тема кластера, keywords, score breakdown и тексты "
        "источников придут в делимитерах <cluster_context>.\n"
        "OUTPUT: editorial_rationale (зачем эти факты), fact_bullets (3-7 "
        "проверяемых утверждений), source_handles (≤5), gaps (≤3 чего не "
        "хватает).\n"
        "HARD RULES:\n"
        "1. Только то, что есть в источниках — не достраивай факты.\n"
        "2. Каждый fact_bullet проверяем (цифра, имя, дата, цитата).\n"
        "3. Если данных нет — пиши это в gaps, не выдумывай.\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_trend_strategist(style: StyleProfile | None) -> str:
    return (
        "MISSION: из фактов исследования выбрать один острый угол подачи для "
        "писателей.\n"
        + _negative_scope("стратег по трендам", only="формулируешь угол")
        + "\nINPUTS: research_brief и score breakdown придут в делимитерах.\n"
        "OUTPUT: editorial_rationale, primary_angle (основной угол), "
        "contrarian_take (контр-тейк, если уместен), why_now (почему сейчас).\n"
        "HARD RULES:\n"
        "1. Угол опирается на конкретный факт из research_brief.\n"
        "2. contrarian_take — narrow disagreement, не broad contrarianism.\n"
        "3. why_now привязан к свежему сигналу, а не к «в наше время».\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_audience_psychology(style: StyleProfile | None) -> str:
    """Phase Q v4 (trimmed) + refactor: bulletproof skeleton, taxonomy names
    kept as a compact reference (not императивы)."""
    return (
        "MISSION: назвать недовысказанную мысль читателя, чтобы писатель попал "
        "в узнавание, а не в убеждение.\n"
        + _negative_scope(
            "аналитик психологии аудитории", only="называешь эмоцию и крючок"
        )
        + "\nINPUTS: angle и audience придут в делимитерах.\n"
        "OUTPUT: editorial_rationale, target_emotion (одно из таксономии ниже), "
        "hook_pattern (один из паттернов ниже), cognitive_bias_lever "
        "(формат «<bias> via <mechanism> at <click_position>», ≤25 слов).\n"
        "HARD RULES:\n"
        f"1. target_emotion ∈ {{{_EMOTION_TAXONOMY_TEXT}}}.\n"
        "2. hook_pattern — ровно один из паттернов-справки ниже.\n"
        f"3. Запрещены мёртвые рычаги: {_DEAD_LEVERS_TEXT}.\n"
        "Паттерны-крючки (справка):\n"
        + _HOOK_PATTERNS_TEXT
        + "\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_platform_writer_telegram(style: StyleProfile | None) -> str:
    """Refactor: bulletproof skeleton, voice from StyleProfile (Style context),
    hook is a first-class field. 10 evasion rules kept as the core mechanical
    guidance; banned-phrase list stays OUT (deterministic detector catches)."""
    return (
        "MISSION: написать готовый к показу Telegram-пост в голосе канала под "
        "выбранный угол и эмоцию.\n"
        + _negative_scope("райтер для Telegram (RU pro, май 2026)", only="пишешь пост")
        + "\nINPUTS: angle, psych и Style context придут в делимитерах. Голос "
        "бери из Style context — это голос конкретного канала.\n"
        "OUTPUT: editorial_rationale, body (лимит 4096, цель 800-1500 — короче "
        "лучше), hook (первые ~80 символов, осознанно спроектированный крючок), "
        "cta.\n"
        "HOOK: продумай в голове 3 варианта первой строки под hook_pattern из "
        "psych, лучший положи в поле hook и поставь его первой строкой body.\n"
        "HARD RULES (compact):\n"
        + _EVASION_RULES_TEXT
        + f"\n\n{_WRITER_ANTI_EXAMPLE}\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_platform_writer_threads(style: StyleProfile | None) -> str:
    """Refactor: bulletproof skeleton; voice from StyleProfile (Style context).
    No banned-list inline (detector catches)."""
    return (
        "MISSION: написать короткий Threads-пост в голосе канала, заточенный "
        "под reply-chain.\n"
        + _negative_scope("райтер для Threads (RU pro)", only="пишешь пост")
        + "\nINPUTS: angle, psych и Style context придут в делимитерах. Голос "
        "бери из Style context.\n"
        "OUTPUT: editorial_rationale, body (лимит 500, цель 180-380), cta.\n"
        "HARD RULES:\n"
        "1. Открой конкретной деталью (имя / число / сцена).\n"
        "2. Одно короткое предложение до 6 слов и одно длинное от 25.\n"
        "3. Минимум одна локатируемая конкретика.\n"
        "4. Заканчивай открытым вопросом конкретному читателю — алгоритм "
        "оптимизирует reply-chain, не лайки.\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_platform_writer_reddit(style: StyleProfile | None) -> str:
    """Refactor: bulletproof skeleton; voice from StyleProfile (Style context)."""
    return (
        "MISSION: написать Reddit-пост (title + body) в голосе канала, язык — "
        "по источнику.\n"
        + _negative_scope("райтер для Reddit (RU + EN)", only="пишешь пост")
        + "\nINPUTS: angle, psych и Style context придут в делимитерах. Голос "
        "бери из Style context.\n"
        "OUTPUT: editorial_rationale, title (60-90, полное утверждение/вопрос, "
        "без clickbait), body (800-2000, TL;DR в конце), cta.\n"
        "HARD RULES (compact):\n"
        + _EVASION_RULES_TEXT
        + f"\n\n{_WRITER_ANTI_EXAMPLE}\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_critic_red_team(style: StyleProfile | None) -> str:
    """Refactor: bulletproof skeleton. Critic receives deterministic_flags via
    user prompt — they ARE the floor. LLM adds editorial judgment on top."""
    return (
        "MISSION: red-team три драфта (TG/Threads/Reddit) и выдать критику для "
        "главного редактора.\n"
        + _negative_scope("критик / red team (RU 2026)", only="оцениваешь драфты")
        + "\nINPUTS: драфты и DETERMINISTIC FLAGS от Python-детектора придут в "
        "делимитерах. Эти флаги — пол: они ОБЯЗАНЫ попасть в length_issues или "
        "factual_concerns и поднять slop_count.\n"
        "OUTPUT: editorial_rationale, slop_count, factual_concerns (≤3), "
        "length_issues (≤3), hook_grade (0-10).\n"
        "HARD RULES (editorial-флаги сверх детектора):\n"
        "1. Слабый крючок (первые 1-2 строки не держат скролл).\n"
        "2. Mismatch target_emotion vs тон текста.\n"
        "3. Нет конкретного якоря (имя, дата, цифра с дробью).\n"
        "4. Wrap-up концовка-пересказ или симметричные тройки «X, Y и Z».\n"
        "hook_grade 0-10: 0-3 серый, 4-6 средний, 7-8 сильный, 9-10 выдающийся.\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_editor_in_chief_draft(style: StyleProfile | None) -> str:
    return (
        "MISSION: собрать финальный brief из лучших версий драфтов с учётом "
        "критики.\n"
        + _negative_scope("главный редактор (Editor-in-Chief)", only="собираешь финал")
        + "\nINPUTS: research, angle, psych, три драфта и critic_report придут "
        "в делимитерах.\n"
        "OUTPUT: editorial_rationale, topic, source_summary, why_it_matters, "
        "psychology_hook, final_tg, final_threads, final_reddit, cta.\n"
        "HARD RULES:\n"
        "1. Бери лучшую версию каждой платформы, учитывай замечания критика.\n"
        "2. Соблюдай лимиты длины под каждую платформу.\n"
        "3. Не добавляй фактов, которых нет в research — ты собираешь, не пишешь.\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_fact_checker(style: StyleProfile | None) -> str:
    """NEW role (audit refactor). Information asymmetry is the point: the
    fact_checker sees the FINAL assembled text + the research facts/sources,
    but NOT the writer's reasoning. Asymmetry is the documented lever that
    reduces hallucination — the checker cannot be talked into a claim by the
    writer's rationale, it can only tie claims to sources."""
    return (
        "MISSION: проверить, что каждый проверяемый claim финального текста "
        "опирается на факт/источник из research_brief.\n"
        + _negative_scope("фактчекер", only="проверяешь привязку claim'ов к источникам")
        + "\nINPUTS: финальный текст придёт в <final_brief>, факты и источники "
        "в <research_facts>. Рассуждений писателя ты НЕ видишь — это намеренно: "
        "оценивай только текст против фактов.\n"
        "OUTPUT: editorial_rationale, unsupported_claims (≤5 — claim'ы финала "
        "без опоры на источник), grounding_score (0..1, доля привязанных "
        "claim'ов).\n"
        "HARD RULES:\n"
        "1. claim считается необоснованным, если его нет в research_facts.\n"
        "2. Не переписывай текст и не оценивай стиль — только grounding.\n"
        "3. Если все claim'ы привязаны — unsupported_claims пустой, "
        "grounding_score близок к 1.0.\n"
        + _RATIONALE_RULE
        + f"\nStyle context: {_format_style(style)}"
        + _safety_block()
    )


def system_quality_judge(style: StyleProfile | None) -> str:
    """Phase Q + refactor: calibrated thresholds, now also consuming the
    fact_checker's grounding signal and scoring the hook (scroll-stop)
    explicitly. Drafts with deterministic AI-tells from the critic cannot
    score high viral regardless of polish — the floor checks ARE the floor."""
    return (
        "MISSION: оценить финальный brief по метрикам (0..1) и дать "
        "recommendation редактору.\n"
        + _negative_scope("Quality Judge (RU editorial 2026)", only="оцениваешь финал")
        + "\nINPUTS: final_brief, critic_report и fact_check придут в "
        "делимитерах. Учитывай deterministic_flags критика и unsupported_claims "
        "фактчекера.\n"
        "OUTPUT: editorial_rationale, style_match_score, viral_score, slop_risk, "
        "controversy_risk, hook_score, recommendation ∈ {approve, revise, reject}.\n"
        "КАЛИБРОВКА (справка):\n"
        "- style_match_score: 0.0 чужой голос … 0.7 соответствует Style DNA … "
        "0.9 фирменный приём.\n"
        "- viral_score: 0.0 пройдут мимо … 0.7 сохранят … 0.85+ перешлют.\n"
        "- slop_risk: 0.0 как человек … 0.8+ очевидно AI. Учитывай "
        "deterministic_flags.\n"
        "- controversy_risk: 0.0 безопасно … 0.8+ риск репутации.\n"
        "- hook_score: scroll-stop первых ~80 символов. 0.0 не держит, "
        "0.5 средне, 0.8+ останавливает скролл и тянет читать дальше.\n"
        "HARD RULES:\n"
        "1. Если unsupported_claims фактчекера не пуст — slop_risk не ниже 0.4 "
        "и recommendation не выше revise.\n"
        "2. approve: viral≥0.75 И slop_risk≤0.30 И controversy_risk≤0.55 И "
        "hook_score≥0.6; revise если slop_risk≤0.50; иначе reject.\n"
        "3. recommendation — рекомендация редактору, НЕ авто-одобрение.\n"
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
        _role_reanchor("аналитик-исследователь")
        + wrap_input("cluster_context", _format_cluster_context(cluster, raw_items))
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
        _role_reanchor("стратег по трендам")
        + wrap_input("research_brief", rb)
        + "\n"
        + wrap_input("score_breakdown", score)
        + "\n\nСформируй: primary_angle (основной угол), contrarian_take "
        "(контр-тейк, если уместен), why_now (почему сейчас). "
        "editorial_rationale ≤ 1500 симв. "
        + SAFETY_FOOTER
    )


def user_audience_psychology(artifacts: dict, style: StyleProfile | None) -> str:
    angle = artifacts.get("angle", {})
    audience = (style.audience if style else "контент-маркетологи и редакторы") or ""
    return (
        _role_reanchor("аналитик психологии аудитории")
        + wrap_input("angle", angle)
        + "\n"
        + wrap_input("audience", audience)
        + "\n\nОпредели target_emotion, hook_pattern, cognitive_bias_lever. "
        "editorial_rationale ≤ 1500. " + SAFETY_FOOTER
    )


def user_platform_writer(artifacts: dict, platform: str, *, style: StyleProfile | None) -> str:
    """Writer user prompt. Voice now comes from the channel's StyleProfile
    (Style context, in delimiters) — NOT from a voice_brief artifact (the
    style_dna_editor step was removed in the role refactor)."""
    angle = artifacts.get("angle", {})
    psych = artifacts.get("psych", {})
    return (
        _role_reanchor(f"райтер для {platform}")
        + wrap_input("angle", angle)
        + "\n"
        + wrap_input("psych", psych)
        + "\n"
        + wrap_input("style_context", _format_style(style))
        + f"\n\nНапиши {platform}-версию в голосе из style_context. Соблюдай "
        "длину под платформу. Поля JSON: editorial_rationale + "
        "(body / hook / cta или title / body / cta). "
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
        _role_reanchor("критик / red team")
        + wrap_input("telegram_draft", tg)
        + "\n"
        + wrap_input("threads_draft", th)
        + "\n"
        + wrap_input("reddit_draft", rd)
        + "\n"
        + wrap_input("deterministic_flags", deterministic_block)
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
        _role_reanchor("главный редактор (Editor-in-Chief)")
        + wrap_input("research_brief", rb)
        + "\n"
        + wrap_input("angle", angle)
        + "\n"
        + wrap_input("psych", psych)
        + "\n"
        + wrap_input("telegram_draft", tg)
        + "\n"
        + wrap_input("threads_draft", th)
        + "\n"
        + wrap_input("reddit_draft", rd)
        + "\n"
        + wrap_input("critic_report", critic)
        + "\n\nСобери final_brief: topic, source_summary (≤2000), "
        "why_it_matters (≤1500), psychology_hook (≤1500), final_tg (≤4096, "
        "цель 600–1500), final_threads (≤500), final_reddit (≤10000, цель "
        "800–3000), cta. Учти замечания критика. editorial_rationale ≤ 1500. "
        + SAFETY_FOOTER
    )


def user_fact_checker(artifacts: dict) -> str:
    """Information-asymmetric fact-check user prompt.

    DELIBERATELY ships ONLY the final_brief text + the research_brief's
    facts/sources. The writer drafts (tg_post/threads_post/reddit_post) and
    all editorial_rationale reasoning are withheld so the checker grounds the
    FINAL claims against sources without being anchored by the writer's
    narrative. This asymmetry is the documented hallucination-reduction lever.
    """
    fb = artifacts.get("final_brief", {})
    rb = artifacts.get("research_brief", {})
    final_text = {
        "topic": fb.get("topic", ""),
        "final_tg": fb.get("final_tg", ""),
        "final_threads": fb.get("final_threads", ""),
        "final_reddit": fb.get("final_reddit", ""),
        "why_it_matters": fb.get("why_it_matters", ""),
    }
    research_facts = {
        "fact_bullets": rb.get("fact_bullets", []),
        "source_handles": rb.get("source_handles", []),
    }
    return (
        _role_reanchor("фактчекер")
        + wrap_input("final_brief", final_text)
        + "\n"
        + wrap_input("research_facts", research_facts)
        + "\n\nПривяжи каждый проверяемый claim финала к источнику. Верни: "
        "unsupported_claims (≤5 claim'ов без опоры), grounding_score (0..1). "
        "editorial_rationale ≤ 1500. " + SAFETY_FOOTER
    )


def user_quality_judge(artifacts: dict) -> str:
    fb = artifacts.get("final_brief", {})
    critic = artifacts.get("critic_report", {})
    fact_check = artifacts.get("fact_check", {})
    return (
        _role_reanchor("Quality Judge")
        + wrap_input("final_brief", fb)
        + "\n"
        + wrap_input("critic_report", critic)
        + "\n"
        + wrap_input("fact_check", fact_check)
        + "\n\nОцени: style_match_score, viral_score, slop_risk, "
        "controversy_risk, hook_score (все в [0, 1]), recommendation ∈ "
        "{approve, revise, reject}. Учитывай unsupported_claims фактчекера. "
        "Помни: recommendation — это рекомендация редактору, НЕ автоматическое "
        "одобрение в продукте. editorial_rationale ≤ 1500. " + SAFETY_FOOTER
    )


__all__ = [
    "SAFETY_FOOTER",
    "SCHEMA_ANGLE",
    "SCHEMA_CRITIC_REPORT",
    "SCHEMA_FACT_CHECK",
    "SCHEMA_FINAL_BRIEF",
    "SCHEMA_PSYCH",
    "SCHEMA_QUALITY_REPORT",
    "SCHEMA_REDDIT_POST",
    "SCHEMA_RESEARCH_BRIEF",
    "SCHEMA_TG_POST",
    "SCHEMA_THREADS_POST",
    "system_audience_psychology",
    "system_critic_red_team",
    "system_editor_in_chief_draft",
    "system_fact_checker",
    "system_platform_writer_reddit",
    "system_platform_writer_telegram",
    "system_platform_writer_threads",
    "system_quality_judge",
    "system_research_analyst",
    "system_trend_strategist",
    "user_audience_psychology",
    "user_critic_red_team",
    "user_editor_in_chief_draft",
    "user_fact_checker",
    "user_platform_writer",
    "user_quality_judge",
    "user_research_analyst",
    "user_trend_strategist",
    "wrap_input",
]
