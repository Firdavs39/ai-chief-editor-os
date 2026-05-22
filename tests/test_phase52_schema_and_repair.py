"""Phase 5.2 — schema lock + validation-aware repair tests.

Phase 5.1 surfaced a Pydantic length-overflow failure on
`PsychArtifact.editorial_rationale` when Kimi K2.6 wrote an honest
multi-sentence rationale that exceeded the 240-char cap. Phase 5.2:

1. Raises schema limits so they reflect platform reality (TG=4096,
   Threads=500, Reddit body=10000, title=300) and gives rationale fields
   editorial breathing room (240 → 1500).
2. Adds ONE targeted retry on NON-length validation errors (enum mismatch,
   missing field, score out of range), with a structured repair prompt.
3. Keeps the hard-fail contract: no silent truncation, no auto-approval,
   no PublishJob creation. Failure paths still produce zero PostCandidate.

These tests lock those guarantees in place.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError
from sqlmodel import select

from chief_editor.llm import registry as llm_registry
from chief_editor.llm.base import LLMProvider
from chief_editor.models import (
    ApprovalDecision,
    PostCandidate,
    PublishJob,
    TrendCluster,
)
from chief_editor.services.generation import (
    advance_one_step,
    enqueue_run,
    run_to_completion_for_tests,
)
from chief_editor.services.generation.artifacts import (
    FinalBriefArtifact,
    RedditPostArtifact,
    TelegramPostArtifact,
    ThreadsPostArtifact,
    validate_payload,
)
from chief_editor.services.generation.workflow import (
    _build_repair_prompt,
    _is_length_only_error,
    _summarize_validation_errors,
)

# ---------------------------------------------------------------------------
# 1. Schema-vs-platform-limit lock (regression guard for future maintainers)
# ---------------------------------------------------------------------------


def _max_length(model: type, field_name: str) -> int:
    """Extract the max_length constraint from a Pydantic v2 field."""
    field = model.model_fields[field_name]
    for m in field.metadata:
        if getattr(m, "max_length", None) is not None:
            return m.max_length
    raise AssertionError(f"{model.__name__}.{field_name} has no max_length")


def test_schema_limits_do_not_exceed_real_platform_limits() -> None:
    """A draft that passes schema MUST be technically publishable on each
    platform. If someone widens these in the future, a candidate could pass
    schema validation but fail at publish time with HTTP 400 — outside the
    safety contour. This test makes that regression a build failure.
    """
    # Telegram Bot API sendMessage hard limit
    assert _max_length(TelegramPostArtifact, "body") <= 4096
    assert _max_length(FinalBriefArtifact, "final_tg") <= 4096

    # Threads platform hard limit
    assert _max_length(ThreadsPostArtifact, "body") <= 500
    assert _max_length(FinalBriefArtifact, "final_threads") <= 500

    # Reddit title hard limit
    assert _max_length(RedditPostArtifact, "title") <= 300

    # Reddit body soft cap (platform allows 40k, we cap at 10k for engagement
    # reasons; if someone wants to raise this they should raise it on
    # purpose, not by accident).
    assert _max_length(RedditPostArtifact, "body") <= 10000
    assert _max_length(FinalBriefArtifact, "final_reddit") <= 10000


def test_editorial_rationale_limit_is_1500_after_phase_52() -> None:
    """Phase 5.2 raised this from 240. The new limit is intentional — small
    enough that hidden chain-of-thought does not fit, large enough that an
    honest multi-sentence editorial rationale does."""
    for model in (
        TelegramPostArtifact,
        ThreadsPostArtifact,
        RedditPostArtifact,
        FinalBriefArtifact,
    ):
        assert _max_length(model, "editorial_rationale") == 1500, (
            f"{model.__name__}.editorial_rationale should be 1500 chars "
            f"after Phase 5.2"
        )


def test_final_brief_metadata_fields_widened() -> None:
    """source_summary / why_it_matters / psychology_hook were 400/300/200 —
    too tight for nuanced operator-facing commentary."""
    assert _max_length(FinalBriefArtifact, "source_summary") >= 2000
    assert _max_length(FinalBriefArtifact, "why_it_matters") >= 1500
    assert _max_length(FinalBriefArtifact, "psychology_hook") >= 1500


def test_validate_payload_rejects_overlong_final_tg_no_silent_truncate() -> None:
    """Schema MUST reject content over the platform limit (no silent
    truncation of creative content). Operator must see the failure."""
    over_tg = "x" * 5000  # > Telegram 4096
    with pytest.raises(ValidationError):
        validate_payload(
            "final_brief",
            {
                "editorial_rationale": "ok",
                "topic": "тест",
                "source_summary": "ok",
                "why_it_matters": "ok",
                "psychology_hook": "ok",
                "final_tg": over_tg,
                "final_threads": "short",
                "final_reddit": "short",
                "cta": "",
            },
        )


def test_validate_payload_accepts_at_platform_limit() -> None:
    """Exact-platform-limit values must validate (boundary case)."""
    payload = validate_payload(
        "final_brief",
        {
            "editorial_rationale": "ok",
            "topic": "тест",
            "source_summary": "ok",
            "why_it_matters": "ok",
            "psychology_hook": "ok",
            "final_tg": "a" * 4096,
            "final_threads": "b" * 500,
            "final_reddit": "c" * 10000,
            "cta": "",
        },
    )
    assert len(payload["final_tg"]) == 4096
    assert len(payload["final_threads"]) == 500
    assert len(payload["final_reddit"]) == 10000


# ---------------------------------------------------------------------------
# 2. _is_length_only_error classifier (unit test)
# ---------------------------------------------------------------------------


def _make_validation_error_from(payload: dict[str, Any], artifact: str) -> ValidationError:
    try:
        validate_payload(artifact, payload)
    except ValidationError as e:
        return e
    raise AssertionError("expected ValidationError")


def test_is_length_only_error_true_for_pure_length_overflow() -> None:
    err = _make_validation_error_from(
        {
            "editorial_rationale": "x" * 2000,  # > 1500
            "primary_angle": "test",
            "contrarian_take": "",
            "why_now": "",
        },
        "angle",
    )
    assert _is_length_only_error(err) is True


def test_is_length_only_error_false_for_enum_mismatch() -> None:
    err = _make_validation_error_from(
        {
            "editorial_rationale": "ok",
            "style_match_score": 0.5,
            "viral_score": 0.5,
            "slop_risk": 0.5,
            "controversy_risk": 0.5,
            "recommendation": "ship_it_now",  # not in {approve, revise, reject}
        },
        "quality_report",
    )
    assert _is_length_only_error(err) is False


def test_is_length_only_error_false_for_out_of_range_score() -> None:
    err = _make_validation_error_from(
        {
            "editorial_rationale": "ok",
            "style_match_score": 5.0,  # > 1.0
            "viral_score": 0.5,
            "slop_risk": 0.5,
            "controversy_risk": 0.5,
            "recommendation": "approve",
        },
        "quality_report",
    )
    assert _is_length_only_error(err) is False


def test_is_length_only_error_false_for_missing_required_field() -> None:
    err = _make_validation_error_from(
        {
            "editorial_rationale": "ok",
            # missing target_emotion / hook_pattern / cognitive_bias_lever
        },
        "psych",
    )
    assert _is_length_only_error(err) is False


def test_is_length_only_error_false_for_mixed_errors() -> None:
    """Length overflow + enum mismatch in the same payload → False (any
    non-length error disqualifies the whole payload from length-only)."""
    err = _make_validation_error_from(
        {
            "editorial_rationale": "x" * 2000,  # length
            "style_match_score": 0.5,
            "viral_score": 0.5,
            "slop_risk": 0.5,
            "controversy_risk": 0.5,
            "recommendation": "nope",  # enum
        },
        "quality_report",
    )
    assert _is_length_only_error(err) is False


# ---------------------------------------------------------------------------
# 3. _summarize_validation_errors — no raw payload, capped length
# ---------------------------------------------------------------------------


def test_summarize_validation_errors_caps_length() -> None:
    """A payload with multiple Pydantic violations produces multiple errors;
    summary must still fit under 400 chars so it's storage-safe."""
    err = _make_validation_error_from(
        {
            "editorial_rationale": "ok",
            "style_match_score": 5.0,  # > 1.0
            "viral_score": -1.0,  # < 0.0
            "slop_risk": 99.0,  # > 1.0
            "controversy_risk": -7.0,  # < 0.0
            "recommendation": "nope",  # invalid enum
        },
        "quality_report",
    )
    # Multiple errors → summary still capped
    assert len(err.errors()) >= 2
    summary = _summarize_validation_errors(err)
    assert len(summary) <= 400


def test_summarize_validation_errors_contains_no_raw_payload() -> None:
    """The summary must reference field names and error types only, never
    raw payload content."""
    secret_marker = "ULTRA_SECRET_PAYLOAD_MARKER_XYZ"
    err = _make_validation_error_from(
        {
            "editorial_rationale": secret_marker + ("x" * 2000),  # length error
            "primary_angle": secret_marker,
            "contrarian_take": "",
            "why_now": "",
        },
        "angle",
    )
    summary = _summarize_validation_errors(err)
    assert secret_marker not in summary


# ---------------------------------------------------------------------------
# 4. _build_repair_prompt — structured, no secret leakage
# ---------------------------------------------------------------------------


def test_build_repair_prompt_includes_allowed_fields_and_safety_footer() -> None:
    from chief_editor.services.generation.steps import get_step_by_name

    step = get_step_by_name("quality_judge")
    err = _make_validation_error_from(
        {
            "editorial_rationale": "ok",
            "style_match_score": 0.5,
            "viral_score": 0.5,
            "slop_risk": 0.5,
            "controversy_risk": 0.5,
            "recommendation": "nope",
        },
        "quality_report",
    )
    prompt = _build_repair_prompt(
        step,
        {
            "editorial_rationale": "ok",
            "recommendation": "nope",
        },
        err,
    )
    # Names the step
    assert "quality_judge" in prompt
    # Lists allowed schema fields
    assert "recommendation" in prompt
    assert "style_match_score" in prompt
    # Safety footer present (defense-in-depth on repair turn too)
    assert "Do not invent facts" in prompt
    assert "Do not publish" in prompt
    assert "Do not approve" in prompt


# ---------------------------------------------------------------------------
# 5. End-to-end: repair fires on non-length error and succeeds
# ---------------------------------------------------------------------------


class _ScriptedProvider(LLMProvider):
    """LLM stub that returns a scripted sequence of responses. After the
    last entry it raises — that catches accidental over-calls."""

    name = "scripted"

    def __init__(self, responses: list[Any]) -> None:
        # Phase 6: base init sets `last_input_tokens`/`last_output_tokens`/
        # `last_model` so the workflow can read usage telemetry.
        super().__init__()
        self.last_model = "scripted"
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        self.calls.append(
            {"system": system, "user": user, "schema": schema, "temperature": temperature}
        )
        if not self.responses:
            raise AssertionError(
                "scripted provider out of responses — over-called by the workflow"
            )
        return self.responses.pop(0)

    def rewrite(self, text: str, mode: str) -> str:
        return text


def _install_scripted_provider(
    monkeypatch: pytest.MonkeyPatch, responses: list[Any]
) -> _ScriptedProvider:
    provider = _ScriptedProvider(responses)
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: provider,
    )
    return provider


def _seed_minimal_cluster(session) -> str:
    """Insert a minimal TrendCluster so research_analyst has something to
    read. The mock collector's seed flow is heavier than we need here."""
    cluster = TrendCluster(
        representative_text="Тестовый кластер для Phase 5.2",
        category="ru",
        keywords=["test", "phase52"],
        score_breakdown={
            "recency": 0.5,
            "engagement": 0.5,
            "novelty": 0.5,
            "source_weight": 0.5,
            "controversy": 0.2,
            "usefulness": 0.5,
            "style_fit": 0.5,
        },
        total_score=0.5,
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)
    return cluster.id


def test_repair_fires_on_type_mismatch_then_succeeds(session, monkeypatch) -> None:
    """Provider returns wrong-type field on first call (a string where the
    schema requires a list — non-length validation error), then a valid
    payload on the repair call. Workflow should accept the repaired output
    and step_index should advance.
    """
    bad_then_good_research = [
        # First attempt: fact_bullets is a string, not a list → list_type error
        {
            "editorial_rationale": "broken",
            "fact_bullets": "this should be a list, but it's a string",
        },
        # Repair attempt: valid
        {
            "editorial_rationale": "fixed",
            "fact_bullets": ["a", "b", "c"],
            "source_handles": ["@s1"],
            "gaps": ["nothing"],
        },
    ]
    provider = _install_scripted_provider(monkeypatch, bad_then_good_research)

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)
    session.refresh(run)

    # After repair, step 0 should have succeeded → step_index advances to 1
    assert run.status == "running", f"run.status={run.status} (expected running)"
    assert run.step_index == 1, f"step_index={run.step_index} (expected 1)"
    # Provider was called exactly twice (original + one repair)
    assert len(provider.calls) == 2


def test_repair_does_not_fire_on_length_only_error(session, monkeypatch) -> None:
    """Length overflow → fail fast, no retry. The schema matches platform
    reality post-Phase-5.2, so a length overflow is a real content problem
    the operator must see, not an artifact to silently repair."""
    over_long = [
        {
            # editorial_rationale > 1500 chars → length error
            "editorial_rationale": "x" * 1600,
            "fact_bullets": ["a", "b", "c"],
            "source_handles": ["@s1"],
            "gaps": ["nothing"],
        }
    ]
    provider = _install_scripted_provider(monkeypatch, over_long)

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)
    session.refresh(run)

    assert run.status == "failed"
    assert run.error_class == "ValidationError"
    # Provider was called exactly ONCE (no repair attempt for length-only)
    assert len(provider.calls) == 1


def test_repair_failure_still_fails_safely(session, monkeypatch) -> None:
    """Both the original and the repair return broken JSON. Run must end
    in `failed`, with zero candidate, zero approval, zero publish job."""
    bad_bad = [
        # First: type mismatch (non-length, triggers repair)
        {"editorial_rationale": "broken 1", "fact_bullets": "not a list"},
        # Repair: still wrong type
        {"editorial_rationale": "broken 2", "fact_bullets": 42},
    ]
    provider = _install_scripted_provider(monkeypatch, bad_bad)

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)
    session.refresh(run)

    assert run.status == "failed"
    assert run.candidate_id is None
    assert run.error_class == "ValidationError"
    # Provider called exactly TWICE (original + one repair, then give up)
    assert len(provider.calls) == 2

    # Safety contract still holds — these tables stay clean across the
    # failure path.
    assert session.exec(select(PostCandidate)).first() is None
    assert session.exec(select(ApprovalDecision)).first() is None
    assert session.exec(select(PublishJob)).first() is None


# ---------------------------------------------------------------------------
# 6. Full mock workflow still succeeds end-to-end (regression)
# ---------------------------------------------------------------------------


def test_full_mock_workflow_still_succeeds(client, session) -> None:
    """The default mock provider produces conforming output for all 11
    steps; the Phase 5.2 schema/prompt changes must not break it."""
    llm_registry.reset_provider_cache()  # use the real cached mock provider
    client.post("/demo/seed")
    cluster = session.exec(select(TrendCluster)).first()
    assert cluster is not None
    runs = enqueue_run(session, cluster_id=cluster.id, top_n=1, requested_by="test")
    run = runs[0]
    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.status == "succeeded", (
        f"mock workflow failed: status={run.status}, error={run.error_message}"
    )
    assert run.candidate_id is not None
    # The workflow itself MUST NOT create an ApprovalDecision or PublishJob
    # for the new candidate (demo seed creates them for OTHER candidates;
    # filter by this run's candidate_id to assert the safety invariant for
    # the workflow-generated draft specifically).
    cand_approvals = session.exec(
        select(ApprovalDecision).where(
            ApprovalDecision.candidate_id == run.candidate_id
        )
    ).all()
    cand_jobs = session.exec(
        select(PublishJob).where(PublishJob.candidate_id == run.candidate_id)
    ).all()
    assert cand_approvals == []
    assert cand_jobs == []


# ---------------------------------------------------------------------------
# 7. Failed run safety properties (regression on Phase 5.2 changes)
# ---------------------------------------------------------------------------


def test_failed_run_creates_zero_candidates_zero_approvals_zero_jobs(
    session, monkeypatch
) -> None:
    """Defense-in-depth: even when our new repair code is in the path,
    failure still produces clean tables. This is the Phase 5.0 invariant
    we MUST NOT regress."""
    # Make repair impossible by returning broken JSON twice (type mismatch).
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: _ScriptedProvider(
            [
                {"editorial_rationale": "broken", "fact_bullets": "not list"},
                {"editorial_rationale": "still broken", "fact_bullets": 42},
            ]
        ),
    )

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]
    advance_one_step(session, run)
    session.refresh(run)

    assert run.status == "failed"
    assert run.candidate_id is None
    assert session.exec(select(PostCandidate)).first() is None
    assert session.exec(select(ApprovalDecision)).first() is None
    assert session.exec(select(PublishJob)).first() is None


# ---------------------------------------------------------------------------
# 8. GenerationArtifact payload never contains raw prompts / completions
# ---------------------------------------------------------------------------


def test_artifact_payload_only_contains_schema_fields(client, session) -> None:
    """The persistence contract: payload is the pydantic dump of the
    validated artifact, not raw model output. After a full mock run, every
    artifact payload's keys must be a subset of its schema's defined fields.
    """
    from chief_editor.models import GenerationArtifact
    from chief_editor.services.generation.artifacts import ARTIFACT_MODELS

    llm_registry.reset_provider_cache()
    client.post("/demo/seed")
    cluster = session.exec(select(TrendCluster)).first()
    runs = enqueue_run(session, cluster_id=cluster.id, top_n=1, requested_by="test")
    run = runs[0]
    run_to_completion_for_tests(session, run, max_steps=20)

    artifacts = session.exec(
        select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
    ).all()
    assert len(artifacts) == 11
    for art in artifacts:
        model = ARTIFACT_MODELS.get(art.name)
        if model is None:
            continue
        allowed_keys = set(model.model_fields.keys())
        actual_keys = set(art.payload.keys())
        leaked = actual_keys - allowed_keys
        assert not leaked, (
            f"artifact {art.name} has keys not in schema: {leaked}"
        )
