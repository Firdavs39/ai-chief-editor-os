"""Phase 2 workflow tests — STEP_SEQUENCE, advance_one_step, finalizer,
and safety invariants. All tests use the mock LLM provider; no live
network calls anywhere.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlmodel import select

from chief_editor.models import (
    ApprovalDecision,
    GenerationArtifact,
    GenerationRun,
    GenerationStep,
    PostCandidate,
    PublishJob,
    StyleProfile,
    SystemLog,
    TrendCluster,
)
from chief_editor.services.generation import (
    STEP_SEQUENCE,
    TOTAL_STEPS,
    advance_one_step,
    enqueue_run,
    run_to_completion_for_tests,
)
from chief_editor.services.generation.artifacts import (
    ARTIFACT_NAMES,
    get_run_artifacts_by_name,
    validate_payload,
)
from chief_editor.services.generation.finalizer import (
    FinalizerError,
    finalize_candidate,
)
from chief_editor.services.generation.prompts import SAFETY_FOOTER
from chief_editor.services.generation.provider_capabilities import (
    LLMCallOptions,
    get_capability,
    options_for_step,
)
from chief_editor.services.generation.steps import (
    STEP_NAMES,
    StepDef,
    get_step_by_name,
)


def _seed(client) -> None:
    client.post("/demo/seed")


def _make_run(session, cluster_id: str | None = None) -> GenerationRun:
    if cluster_id is None:
        cluster = session.exec(select(TrendCluster)).first()
        cluster_id = cluster.id if cluster else None
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="manual")
    return runs[0]


# ---------------------------------------------------------------------------
# STEP_SEQUENCE shape
# ---------------------------------------------------------------------------


def test_step_sequence_order_and_count() -> None:
    expected = (
        "research_analyst",
        "trend_strategist",
        "audience_psychology_analyst",
        "style_dna_editor",
        "platform_writer_telegram",
        "platform_writer_threads",
        "platform_writer_reddit",
        "critic_red_team",
        "editor_in_chief_draft",
        "quality_judge",
        "finalizer",
    )
    assert expected == STEP_NAMES
    assert TOTAL_STEPS == 11
    assert len(STEP_SEQUENCE) == 11


def test_finalizer_is_not_an_llm_step() -> None:
    finalizer = get_step_by_name("finalizer")
    assert isinstance(finalizer, StepDef)
    assert finalizer.is_llm is False
    assert finalizer.system_builder is None
    assert finalizer.schema is None


def test_quality_judge_uses_judge_temperature() -> None:
    judge = get_step_by_name("quality_judge")
    assert judge is not None and judge.is_judge is True
    critic = get_step_by_name("critic_red_team")
    assert critic is not None and critic.is_judge is True


def test_every_llm_step_schema_uses_editorial_rationale_not_reasoning_summary() -> None:
    for step in STEP_SEQUENCE:
        if not step.is_llm or step.schema is None:
            continue
        required = step.schema.get("required") or []
        # editorial_rationale must be present
        assert "editorial_rationale" in required, (
            f"step {step.name} schema missing editorial_rationale"
        )
        # reasoning_summary must NOT be present anywhere
        assert "reasoning_summary" not in required, (
            f"step {step.name} still has reasoning_summary"
        )
        props = step.schema.get("properties") or {}
        assert "reasoning_summary" not in props, (
            f"step {step.name} schema properties leak reasoning_summary"
        )


def test_every_llm_step_artifact_name_is_registered() -> None:
    for step in STEP_SEQUENCE:
        assert step.artifact_name in ARTIFACT_NAMES, (
            f"step {step.name} artifact {step.artifact_name} missing from ARTIFACT_NAMES"
        )


# ---------------------------------------------------------------------------
# Prompts: safety footer + no-publish/no-approve
# ---------------------------------------------------------------------------


def test_every_llm_step_system_prompt_includes_safety_footer() -> None:
    style = StyleProfile(name="default", tone="экспертный", audience="редакторы")
    for step in STEP_SEQUENCE:
        if step.system_builder is None:
            continue
        sysp = step.system_builder(style)
        assert SAFETY_FOOTER in sysp, f"step {step.name} system prompt missing safety footer"
        assert "Do not invent facts" in sysp
        assert "Do not publish" in sysp
        assert "Do not approve" in sysp


def test_no_prompt_references_secrets_or_admin_token() -> None:
    style = StyleProfile(name="default", tone="экспертный", audience="редакторы")
    for step in STEP_SEQUENCE:
        if step.system_builder is None:
            continue
        sysp = step.system_builder(style).lower()
        for forbidden in (
            "master_encryption_key",
            "admin_token",
            "anthropic_api_key",
            "openai_api_key",
            "ollama_api_key",
            "telegram_bot_token",
            "decrypt",
            "x-admin-token",
        ):
            assert forbidden not in sysp, (
                f"step {step.name} system prompt references {forbidden}"
            )


# ---------------------------------------------------------------------------
# Provider capabilities
# ---------------------------------------------------------------------------


def test_capabilities_for_all_providers() -> None:
    for name in ("mock", "ollama", "anthropic", "openai"):
        cap = get_capability(name)
        assert cap.name == name
        # Phase 2: native structured output is OFF for everyone (spike)
        assert cap.supports_native_structured_output is False


def test_options_for_step_uses_judge_temperature_when_judge() -> None:
    creative = options_for_step("ollama", "platform_writer_telegram", is_judge=False)
    judge = options_for_step("ollama", "quality_judge", is_judge=True)
    assert creative.temperature == 0.7
    assert judge.temperature == 0.2
    assert creative.step_name == "platform_writer_telegram"
    assert judge.step_name == "quality_judge"


def test_options_for_step_returns_llm_call_options_with_response_mode_json() -> None:
    opts = options_for_step("mock", "research_analyst")
    assert isinstance(opts, LLMCallOptions)
    assert opts.response_mode == "json"
    assert opts.provider_mode == "auto"


def test_mock_capability_is_deterministic() -> None:
    cap = get_capability("mock")
    assert cap.default_temperature == 0.0
    assert cap.judge_temperature == 0.0


# ---------------------------------------------------------------------------
# advance_one_step — incremental behavior
# ---------------------------------------------------------------------------


def test_advance_one_step_creates_generation_step_row(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    advance_one_step(session, run)
    steps = list(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    )
    assert len(steps) == 1
    assert steps[0].name == "research_analyst"
    assert steps[0].status == "succeeded"


def test_advance_one_step_saves_generation_artifact(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    advance_one_step(session, run)
    artifacts = list(
        session.exec(
            select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
        ).all()
    )
    assert len(artifacts) == 1
    assert artifacts[0].name == "research_brief"
    payload = artifacts[0].payload
    assert "editorial_rationale" in payload
    assert "reasoning_summary" not in payload
    assert "fact_bullets" in payload


def test_advance_one_step_flips_queued_to_running_then_advances_index(
    client, session
) -> None:
    _seed(client)
    run = _make_run(session)
    assert run.status == "queued"
    advance_one_step(session, run)
    session.refresh(run)
    assert run.status == "running"
    assert run.step_index == 1
    assert run.current_step == "research_analyst"
    assert run.provider == "mock"


def test_terminal_run_does_not_advance(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    run.status = "succeeded"
    session.add(run)
    session.commit()
    # advance_one_step is a no-op on terminal runs.
    advance_one_step(session, run)
    steps = list(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    )
    assert steps == []


# ---------------------------------------------------------------------------
# Cancellation — no LLM call after cancel
# ---------------------------------------------------------------------------


def test_cancelled_run_does_not_call_llm(client, session, monkeypatch) -> None:
    """Once a run is cancelled, advance_one_step must short-circuit before
    calling complete_json. We patch the mock provider with a tripwire."""
    from chief_editor.llm import registry as reg

    _seed(client)
    run = _make_run(session)

    # Flip to cancelled BEFORE any advance.
    run.status = "cancelled"
    session.add(run)
    session.commit()

    # If anything calls complete_json after cancellation, fail loudly.
    provider = reg.get_llm_provider()
    calls = {"n": 0}

    def _spy(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError(
            "complete_json must NOT be called on a cancelled run"
        )

    monkeypatch.setattr(provider, "complete_json", _spy)

    advance_one_step(session, run)
    assert calls["n"] == 0


def test_cancel_mid_run_stops_subsequent_steps(client, session, monkeypatch) -> None:
    """Run two steps, then cancel, then advance: must NOT call complete_json."""
    from chief_editor.llm import registry as reg

    _seed(client)
    run = _make_run(session)
    advance_one_step(session, run)
    advance_one_step(session, run)
    session.refresh(run)
    assert run.step_index >= 1
    assert run.status == "running"

    # Cancel.
    run.status = "cancelled"
    session.add(run)
    session.commit()

    provider = reg.get_llm_provider()
    calls = {"n": 0}

    def _spy(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("LLM called after cancellation")

    monkeypatch.setattr(provider, "complete_json", _spy)
    advance_one_step(session, run)
    assert calls["n"] == 0


# ---------------------------------------------------------------------------
# Failure semantics — failed step marks run failed and creates no candidate
# ---------------------------------------------------------------------------


def test_failed_step_marks_run_failed_with_no_post_candidate(
    client, session, monkeypatch
) -> None:
    from chief_editor.llm import registry as reg

    _seed(client)
    run = _make_run(session)
    cand_before = len(session.exec(select(PostCandidate)).all())

    provider = reg.get_llm_provider()

    def _boom(*args, **kwargs):
        raise RuntimeError("upstream went sideways")

    monkeypatch.setattr(provider, "complete_json", _boom)

    advance_one_step(session, run)
    session.refresh(run)
    assert run.status == "failed"
    assert run.error_class == "RuntimeError"
    assert run.error_message.startswith("upstream went sideways")
    assert run.candidate_id is None

    cand_after = len(session.exec(select(PostCandidate)).all())
    assert cand_after == cand_before


def test_failed_step_truncates_error_message_to_240_chars(
    client, session, monkeypatch
) -> None:
    from chief_editor.llm import registry as reg

    _seed(client)
    run = _make_run(session)
    provider = reg.get_llm_provider()
    long_msg = "x" * 500

    def _boom(*args, **kwargs):
        raise ValueError(long_msg)

    monkeypatch.setattr(provider, "complete_json", _boom)
    advance_one_step(session, run)
    session.refresh(run)
    assert len(run.error_message) <= 240


# ---------------------------------------------------------------------------
# Finalizer — prerequisites + PostCandidate creation
# ---------------------------------------------------------------------------


def test_finalizer_raises_without_required_artifacts(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    with pytest.raises(FinalizerError):
        finalize_candidate(session, run)


def test_finalizer_creates_draft_post_candidate(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    # Run all 11 steps end-to-end via the test helper.
    run = run_to_completion_for_tests(session, run, max_steps=15)
    assert run.status == "succeeded"
    assert run.candidate_id is not None
    cand = session.get(PostCandidate, run.candidate_id)
    assert cand is not None
    assert cand.status == "draft"
    assert cand.topic
    assert cand.tg_version
    assert cand.threads_version
    assert isinstance(cand.critic_notes, list)


# ---------------------------------------------------------------------------
# Full mock workflow — end-to-end safety
# ---------------------------------------------------------------------------


def test_full_mock_workflow_creates_exactly_one_draft_candidate(
    client, session
) -> None:
    _seed(client)
    cand_before = len(session.exec(select(PostCandidate)).all())
    run = _make_run(session)
    run = run_to_completion_for_tests(session, run)
    cand_after = list(session.exec(select(PostCandidate)).all())
    assert len(cand_after) == cand_before + 1
    new_cand = next(c for c in cand_after if c.id == run.candidate_id)
    assert new_cand.status == "draft"


def test_full_mock_workflow_creates_no_approval_or_publish_job(
    client, session
) -> None:
    _seed(client)
    appr_before = len(session.exec(select(ApprovalDecision)).all())
    job_before = len(session.exec(select(PublishJob)).all())
    run = _make_run(session)
    run_to_completion_for_tests(session, run)
    assert len(session.exec(select(ApprovalDecision)).all()) == appr_before
    assert len(session.exec(select(PublishJob)).all()) == job_before


def test_full_mock_workflow_persists_all_eleven_steps(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    run = run_to_completion_for_tests(session, run)
    steps = list(
        session.exec(
            select(GenerationStep)
            .where(GenerationStep.run_id == run.id)
            .order_by(GenerationStep.step_index.asc())
        ).all()
    )
    assert len(steps) == 11
    assert all(s.status == "succeeded" for s in steps)
    assert [s.name for s in steps] == list(STEP_NAMES)


def test_full_mock_workflow_persists_all_eleven_artifacts(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    run = run_to_completion_for_tests(session, run)
    artifacts = get_run_artifacts_by_name(session, run)
    expected = {
        "research_brief",
        "angle",
        "psych",
        "voice_brief",
        "tg_post",
        "threads_post",
        "reddit_post",
        "critic_report",
        "final_brief",
        "quality_report",
        "candidate_link",
    }
    assert set(artifacts.keys()) == expected


def test_no_artifact_payload_contains_raw_prompt_or_completion(
    client, session
) -> None:
    """Artifact payloads must only contain the canonical schema fields.
    No prompt body, no system instruction, no raw model text."""
    _seed(client)
    run = _make_run(session)
    run = run_to_completion_for_tests(session, run)
    artifacts = list(
        session.exec(
            select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
        ).all()
    )
    for a in artifacts:
        blob = str(a.payload)
        # Safety footer is in prompts, never in artifacts.
        assert SAFETY_FOOTER not in blob, (
            f"artifact {a.name} contains the prompt safety footer"
        )
        # Mandatory prompt fragments must not leak.
        assert "Style context:" not in blob
        assert "Тема кластера:" not in blob


def test_systemlog_generation_events_use_whitelist_only(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    run_to_completion_for_tests(session, run)
    allowed = {"run_id", "status", "step_count", "duration_ms", "error_class"}
    rows = list(
        session.exec(
            select(SystemLog).where(SystemLog.event.like("generation.%"))  # type: ignore[attr-defined]
        ).all()
    )
    assert rows
    for row in rows:
        for key in row.data or {}:
            assert key in allowed, (
                f"generation.* SystemLog has non-whitelisted key {key} in {row.event}"
            )


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def test_validate_payload_rejects_unknown_artifact_name() -> None:
    with pytest.raises(ValueError):
        validate_payload("not_a_real_artifact", {})


def test_validate_payload_clamps_editorial_rationale_at_240() -> None:
    too_long = "x" * 300
    with pytest.raises(ValidationError):
        validate_payload(
            "angle",
            {
                "editorial_rationale": too_long,
                "primary_angle": "test",
                "contrarian_take": "",
                "why_now": "",
            },
        )


def test_validate_payload_quality_report_enum_recommendation() -> None:
    with pytest.raises(ValidationError):
        validate_payload(
            "quality_report",
            {
                "editorial_rationale": "test",
                "style_match_score": 0.5,
                "viral_score": 0.5,
                "slop_risk": 0.5,
                "controversy_risk": 0.5,
                "recommendation": "ship-it-now",
            },
        )


# ---------------------------------------------------------------------------
# Transaction ownership — workflow.py owns the finalizer step's transaction.
# ---------------------------------------------------------------------------


def test_finalizer_does_not_commit_independently(client, session) -> None:
    """The finalizer must stage the PostCandidate and run.candidate_id but
    leave the commit to the workflow engine. We exercise this by calling
    `finalize_candidate` directly on a fully-staged run, then rolling back
    BEFORE the workflow would normally commit. The PostCandidate must NOT
    persist."""
    from sqlmodel import select as _select

    from chief_editor.models import GenerationArtifact as _Artifact
    from chief_editor.models import GenerationStep as _Step

    _seed(client)
    run = _make_run(session)

    # Manually seed the prerequisites the finalizer needs: a final_brief and
    # quality_report artifact. We don't go through the full LLM workflow
    # here — we want to isolate the transactional behavior.
    research_step = _Step(run_id=run.id, step_index=0, name="placeholder", status="succeeded")
    session.add(research_step)
    session.commit()
    session.refresh(research_step)

    session.add(
        _Artifact(
            run_id=run.id,
            step_id=research_step.id,
            name="final_brief",
            payload={
                "editorial_rationale": "test",
                "topic": "Тестовая тема",
                "source_summary": "summary",
                "why_it_matters": "matters",
                "psychology_hook": "hook",
                "final_tg": "tg body",
                "final_threads": "threads body",
                "final_reddit": "reddit body",
                "cta": "Сохрани.",
            },
        )
    )
    session.add(
        _Artifact(
            run_id=run.id,
            step_id=research_step.id,
            name="quality_report",
            payload={
                "editorial_rationale": "ok",
                "style_match_score": 0.8,
                "viral_score": 0.7,
                "slop_risk": 0.1,
                "controversy_risk": 0.05,
                "recommendation": "approve",
            },
        )
    )
    session.commit()

    candidates_before = len(session.exec(_select(PostCandidate)).all())

    # Call finalizer directly. It MUST NOT commit.
    payload = finalize_candidate(session, run)
    assert "candidate_id" in payload

    # Roll back. If the finalizer had committed independently the candidate
    # would survive this rollback — that's the bug we are guarding against.
    session.rollback()

    candidates_after = len(session.exec(_select(PostCandidate)).all())
    assert candidates_after == candidates_before, (
        "PostCandidate persisted across rollback — finalizer committed independently"
    )

    # The staged run.candidate_id should also be rolled back.
    session.refresh(run)
    assert run.candidate_id is None


def test_post_finalizer_failure_does_not_create_orphan_post_candidate(
    client, session, monkeypatch
) -> None:
    """Run the full workflow through step 10, then inject a failure AFTER
    `finalize_candidate` returns but BEFORE the workflow commits step 11.
    The PostCandidate must not persist, and the run must be marked failed
    with candidate_id=None."""
    from chief_editor.services.generation import workflow as workflow_module

    _seed(client)
    run = _make_run(session)
    candidates_before = len(session.exec(select(PostCandidate)).all())
    approvals_before = len(session.exec(select(ApprovalDecision)).all())
    jobs_before = len(session.exec(select(PublishJob)).all())

    # Wrap the real _execute_finalizer_step so it does its full work
    # (adds PostCandidate, sets run.candidate_id) and then raises. The
    # workflow's except handler should rollback and clean up.
    real_finalizer = workflow_module._execute_finalizer_step

    def _boom_after_finalizer(session, run):
        real_finalizer(session, run)
        raise RuntimeError("simulated post-finalizer failure")

    monkeypatch.setattr(
        workflow_module, "_execute_finalizer_step", _boom_after_finalizer
    )

    run = run_to_completion_for_tests(session, run, max_steps=20)

    assert run.status == "failed"
    assert run.error_class == "RuntimeError"
    assert "simulated post-finalizer failure" in run.error_message
    assert run.candidate_id is None, "run.candidate_id leaked across the failure"

    # No new PostCandidate, no ApprovalDecision, no PublishJob.
    assert len(session.exec(select(PostCandidate)).all()) == candidates_before, (
        "orphan PostCandidate persisted after post-finalizer failure"
    )
    assert len(session.exec(select(ApprovalDecision)).all()) == approvals_before
    assert len(session.exec(select(PublishJob)).all()) == jobs_before

    # The candidate_link artifact must also be absent (workflow would have
    # added it after the finalizer succeeded, but the failure prevented
    # the commit). Steps 1-10 artifacts are committed earlier (one commit
    # per step), so they should be present.
    artifacts = list(
        session.exec(
            select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
        ).all()
    )
    names = {a.name for a in artifacts}
    assert "candidate_link" not in names
    # Verify the prior steps' artifacts did survive (per-step commit).
    assert {"research_brief", "final_brief", "quality_report"}.issubset(names)


def test_full_mock_workflow_still_creates_exactly_one_draft_post_candidate(
    client, session
) -> None:
    """Regression for the hotfix: with the finalizer no longer committing
    independently, the happy path still produces exactly one PostCandidate
    via the workflow engine's single commit at the end of step 11."""
    _seed(client)
    candidates_before = len(session.exec(select(PostCandidate)).all())
    approvals_before = len(session.exec(select(ApprovalDecision)).all())
    jobs_before = len(session.exec(select(PublishJob)).all())

    run = _make_run(session)
    run = run_to_completion_for_tests(session, run)

    assert run.status == "succeeded"
    assert run.candidate_id is not None

    cands_after = list(session.exec(select(PostCandidate)).all())
    assert len(cands_after) == candidates_before + 1
    new_cand = next(c for c in cands_after if c.id == run.candidate_id)
    assert new_cand.status == "draft"

    assert len(session.exec(select(ApprovalDecision)).all()) == approvals_before
    assert len(session.exec(select(PublishJob)).all()) == jobs_before


def test_finalizer_source_has_no_session_commit_call() -> None:
    """AST guard: the finalizer module must not invoke session.commit().
    Future maintainers will hit this test if they reintroduce the bug.
    Docstring mentions of session.commit() are allowed — only actual
    Attribute call expressions count."""
    import ast
    import inspect

    from chief_editor.services.generation import finalizer as fmod

    tree = ast.parse(inspect.getsource(fmod))
    offending: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match `<anything>.commit(...)` where the attribute name is `commit`.
        if isinstance(func, ast.Attribute) and func.attr == "commit":
            offending.append(f"line {getattr(node, 'lineno', '?')}: {ast.unparse(node)}")
    assert offending == [], (
        f"finalizer.py contains commit() calls: {offending}"
    )
