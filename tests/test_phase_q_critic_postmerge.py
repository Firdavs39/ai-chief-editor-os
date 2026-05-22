"""Phase Q v5 — critic-step post-merge of deterministic AI-tells flags.

After the LLM critic returns its `critic_report`, Python re-runs the
deterministic AI-tells detector on the same drafts and merges findings
into the payload (Sierra "Jiminy Cricket" output-supervisor pattern).

This pin-tests the merge logic — it MUST surface mechanical AI-tells
even when the LLM critic returns a sanitized / lenient report.
"""
from __future__ import annotations

from chief_editor.services.generation.workflow import (
    _merge_deterministic_flags_into_critic,
)


# ---------------------------------------------------------------------------
# Drafts pre-built to exercise the detector
# ---------------------------------------------------------------------------


def _clean_drafts() -> dict[str, dict]:
    """Drafts that should NOT trigger deterministic flags (or trigger very
    few). Used to ensure merge doesn't over-fire."""
    return {
        "tg_post": {
            "body": (
                "76,3% продактов из выборки 47 кампаний не пишут спецификации. "
                "Стоп. Это не лень, это структурный симптом. Я три месяца ходил "
                "по этим граблям и проверял на двух командах. Цифры не врут, а "
                "выводы из них иногда выводят не туда."
            ),
        },
        "threads_post": {
            "body": (
                "76,3% PMов в выборке за 2024 без spec. "
                "А у вас в команде кто пишет?"
            ),
        },
        "reddit_post": {
            "body": (
                "76,3% PM-ов в выборке за 2024 год не пишут спецификации. "
                "Это не история про лень, это про структурный сдвиг к "
                "documentation-as-code в стиле Notion и Linear."
            ),
        },
    }


def _dirty_drafts() -> dict[str, dict]:
    """Drafts that SHOULD trigger deterministic flags."""
    return {
        "tg_post": {
            "body": (
                "В современном мире — стоит отметить — компании играют "
                "ключевую роль в цифровизации — также важно понимать что — "
                "таким образом — подводя итог нужно — давайте погрузимся."
            ),
        },
        "threads_post": {
            "body": "Не секрет, что в современном мире технологии меняют всё.",
        },
        "reddit_post": {
            "body": (
                "В заключение можно сделать вывод: давайте разберём, как "
                "комплексный подход открывает новые горизонты."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_merge_adds_flags_when_critic_understates() -> None:
    """The LLM critic returns slop_count=0 with no length_issues, but
    drafts are AI-tell-heavy. Post-merge MUST surface the flags."""
    artifacts = _dirty_drafts()
    sanitized_critic_payload = {
        "editorial_rationale": "Looks fine to me.",
        "slop_count": 0,
        "factual_concerns": [],
        "length_issues": [],
        "hook_grade": 8,
    }
    merged = _merge_deterministic_flags_into_critic(
        sanitized_critic_payload, artifacts
    )
    # slop_count should jump up (detector found multiple tells across 3 platforms)
    assert merged["slop_count"] > 0, (
        f"deterministic merge didn't surface flags: {merged}"
    )
    # length_issues should now contain detector findings (capped at 3)
    assert len(merged["length_issues"]) > 0
    assert len(merged["length_issues"]) <= 3
    # Each flag should mention a platform prefix
    for flag in merged["length_issues"]:
        assert any(p in flag for p in ("[telegram]", "[threads]", "[reddit]"))


def test_merge_preserves_llm_critic_findings() -> None:
    """If the LLM critic already added editorial findings, merge keeps
    them and may add deterministic ones up to the cap."""
    artifacts = _dirty_drafts()
    critic_payload = {
        "editorial_rationale": "Several issues found.",
        "slop_count": 2,  # LLM caught 2 things
        "factual_concerns": ["Statistic 71% unverified"],
        "length_issues": ["TG body 1300 chars exceeds soft target"],
        "hook_grade": 5,
    }
    merged = _merge_deterministic_flags_into_critic(critic_payload, artifacts)
    # LLM's existing length_issue should still be there
    assert "TG body 1300 chars exceeds soft target" in merged["length_issues"]
    # factual_concerns is NOT touched by merge
    assert "Statistic 71% unverified" in merged["factual_concerns"]
    # slop_count is max(LLM=2, detector_count) — detector found ≥3 in dirty drafts
    assert merged["slop_count"] >= 2


def test_merge_does_not_overfire_on_clean_drafts() -> None:
    """Clean drafts → detector finds nothing or very little → merge
    doesn't inflate the report falsely."""
    artifacts = _clean_drafts()
    critic_payload = {
        "editorial_rationale": "Solid draft.",
        "slop_count": 0,
        "factual_concerns": [],
        "length_issues": [],
        "hook_grade": 8,
    }
    merged = _merge_deterministic_flags_into_critic(critic_payload, artifacts)
    # Clean drafts → merge should add ZERO flags to length_issues
    assert merged["length_issues"] == [], (
        f"merge over-fired on clean drafts: {merged['length_issues']}"
    )
    # slop_count stays 0 (no false positives)
    assert merged["slop_count"] == 0


def test_merge_caps_length_issues_at_schema_max_3() -> None:
    """The Pydantic schema accepts ≤3 length_issues. Merge respects this."""
    artifacts = _dirty_drafts()
    critic_payload = {
        "editorial_rationale": "ok",
        "slop_count": 0,
        "factual_concerns": [],
        "length_issues": ["existing issue 1", "existing issue 2"],
        "hook_grade": 5,
    }
    merged = _merge_deterministic_flags_into_critic(critic_payload, artifacts)
    assert len(merged["length_issues"]) <= 3


def test_merge_does_not_mutate_factual_concerns() -> None:
    """factual_concerns is editorial judgement, not mechanical. Merge
    must NOT touch it."""
    artifacts = _dirty_drafts()
    critic_payload = {
        "editorial_rationale": "ok",
        "slop_count": 0,
        "factual_concerns": ["LLM-found factual issue"],
        "length_issues": [],
        "hook_grade": 5,
    }
    merged = _merge_deterministic_flags_into_critic(critic_payload, artifacts)
    assert merged["factual_concerns"] == ["LLM-found factual issue"]


def test_merge_handles_missing_artifacts() -> None:
    """If a draft artifact is missing (e.g., earlier step failed), merge
    doesn't crash — just skips the missing platform."""
    artifacts = {
        "tg_post": {"body": "В современном мире что-то."},
        # threads_post / reddit_post missing
    }
    critic_payload = {
        "editorial_rationale": "ok",
        "slop_count": 0,
        "factual_concerns": [],
        "length_issues": [],
        "hook_grade": 5,
    }
    merged = _merge_deterministic_flags_into_critic(critic_payload, artifacts)
    # Should fire on TG only (the Tier-1 opener)
    assert any("[telegram]" in f for f in merged["length_issues"])
    assert merged["slop_count"] > 0
