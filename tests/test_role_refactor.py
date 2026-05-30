"""Role-refactor tests (audit, May 2026).

Covers the four guarantees the refactor must hold:
1. `fact_checker` is present, sits between editor_in_chief_draft and
   quality_judge, and emits the FactCheck schema.
2. `style_dna_editor` / `voice_brief` are GONE and the pipeline still runs
   to a draft candidate without them.
3. Per-role temperature is applied (writer 0.6 / evaluator 0.2 / analyst 0.3
   for real providers; mock stays deterministic 0.0).
4. A synthetic mock run traverses the NEW 11-step sequence end-to-end.

All tests use the mock provider or a local recording stub — zero network.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import select

from chief_editor.llm.base import LLMProvider
from chief_editor.models import (
    ApprovalDecision,
    GenerationArtifact,
    GenerationStep,
    PostCandidate,
    PublishJob,
    TrendCluster,
)
from chief_editor.services.generation import (
    STEP_SEQUENCE,
    TOTAL_STEPS,
    enqueue_run,
    run_to_completion_for_tests,
)
from chief_editor.services.generation.artifacts import (
    ARTIFACT_MODELS,
    ARTIFACT_NAMES,
    FactCheckArtifact,
    validate_payload,
)
from chief_editor.services.generation.prompts import (
    SAFETY_FOOTER,
    SCHEMA_FACT_CHECK,
    system_fact_checker,
    user_fact_checker,
    wrap_input,
)
from chief_editor.services.generation.provider_capabilities import (
    ANALYST_TEMPERATURE,
    EVALUATOR_TEMPERATURE,
    WRITER_TEMPERATURE,
    temperature_for_role,
)
from chief_editor.services.generation.steps import STEP_NAMES, get_step_by_name


def _seed(client) -> None:
    client.post("/demo/seed")


def _make_run(session):
    cluster = session.exec(select(TrendCluster)).first()
    cluster_id = cluster.id if cluster else None
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="manual")
    return runs[0]


# ---------------------------------------------------------------------------
# 1. fact_checker present + schema
# ---------------------------------------------------------------------------


def test_fact_checker_step_present_and_positioned() -> None:
    step = get_step_by_name("fact_checker")
    assert step is not None
    assert step.is_llm is True
    assert step.is_judge is True  # evaluator band
    assert step.artifact_name == "fact_check"
    assert step.schema is SCHEMA_FACT_CHECK
    # Order: editor assembles → fact_checker grounds → judge scores.
    idx = {s.name: i for i, s in enumerate(STEP_SEQUENCE)}
    assert idx["editor_in_chief_draft"] < idx["fact_checker"] < idx["quality_judge"]
    assert idx["fact_checker"] == idx["editor_in_chief_draft"] + 1


def test_fact_check_artifact_is_registered() -> None:
    assert "fact_check" in ARTIFACT_NAMES
    assert ARTIFACT_MODELS["fact_check"] is FactCheckArtifact


def test_fact_check_schema_fields() -> None:
    required = set(SCHEMA_FACT_CHECK["required"])
    assert required == {"editorial_rationale", "unsupported_claims", "grounding_score"}
    props = SCHEMA_FACT_CHECK["properties"]
    assert props["grounding_score"]["minimum"] == 0
    assert props["grounding_score"]["maximum"] == 1
    assert props["unsupported_claims"]["maxItems"] == 5


def test_fact_check_validate_payload_roundtrip() -> None:
    payload = validate_payload(
        "fact_check",
        {
            "editorial_rationale": "Все claim'ы привязаны к источникам.",
            "unsupported_claims": ["claim без источника"],
            "grounding_score": 0.8,
        },
    )
    assert payload["grounding_score"] == 0.8
    assert payload["unsupported_claims"] == ["claim без источника"]


def test_fact_checker_system_prompt_is_information_asymmetric() -> None:
    """The fact_checker must be told it does NOT see the writer's reasoning
    and must include the safety footer like every other role."""
    sysp = system_fact_checker(None)
    assert SAFETY_FOOTER in sysp
    # Information asymmetry: it grounds against research facts, not the
    # writer's rationale.
    assert "research_facts" in sysp
    assert "final_brief" in sysp
    # Budget: analytic/judging prompts stay compact.
    assert len(sysp) < 4000


def test_fact_checker_user_prompt_withholds_writer_drafts() -> None:
    """Information asymmetry guard: the fact_checker user prompt must carry
    the final text + research facts but NOT the writer drafts or their
    editorial_rationale narrative."""
    artifacts = {
        "final_brief": {
            "topic": "тема",
            "final_tg": "Финальный TG-текст с цифрой 76,3%.",
            "final_threads": "Финальный Threads.",
            "final_reddit": "Финальный Reddit.",
            "why_it_matters": "почему важно",
            # This editorial_rationale belongs to the editor; it must NOT be
            # forwarded to the fact_checker (it's writer-side reasoning).
            "editorial_rationale": "СЕКРЕТНОЕ_РАССУЖДЕНИЕ_РЕДАКТОРА",
        },
        "research_brief": {
            "fact_bullets": ["76,3% по выборке"],
            "source_handles": ["@src"],
        },
        # Writer drafts — must NOT leak into the fact_checker prompt.
        "tg_post": {"body": "ЧЕРНОВИК_ПИСАТЕЛЯ_TG", "editorial_rationale": "draft-think"},
        "threads_post": {"body": "ЧЕРНОВИК_ПИСАТЕЛЯ_THREADS"},
        "reddit_post": {"body": "ЧЕРНОВИК_ПИСАТЕЛЯ_REDDIT"},
    }
    prompt = user_fact_checker(artifacts)
    # Final text + facts present.
    assert "76,3%" in prompt
    assert "@src" in prompt
    # Writer drafts + editor rationale withheld.
    assert "ЧЕРНОВИК_ПИСАТЕЛЯ_TG" not in prompt
    assert "ЧЕРНОВИК_ПИСАТЕЛЯ_THREADS" not in prompt
    assert "ЧЕРНОВИК_ПИСАТЕЛЯ_REDDIT" not in prompt
    assert "СЕКРЕТНОЕ_РАССУЖДЕНИЕ_РЕДАКТОРА" not in prompt
    # Role re-anchor present.
    assert prompt.startswith("Действуй строго как фактчекер.")


def test_full_run_persists_fact_check_artifact(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.status == "succeeded"
    artifacts = list(
        session.exec(
            select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
        ).all()
    )
    by_name = {a.name: a.payload for a in artifacts}
    assert "fact_check" in by_name
    fc = by_name["fact_check"]
    assert "grounding_score" in fc
    assert "unsupported_claims" in fc
    assert isinstance(fc["unsupported_claims"], list)


# ---------------------------------------------------------------------------
# 2. voice_brief / style_dna_editor gone; pipeline does not break
# ---------------------------------------------------------------------------


def test_style_dna_editor_removed_everywhere() -> None:
    assert "style_dna_editor" not in STEP_NAMES
    assert get_step_by_name("style_dna_editor") is None
    # voice_brief is no longer a produced artifact.
    assert "voice_brief" not in ARTIFACT_NAMES
    assert "voice_brief" not in ARTIFACT_MODELS


def test_prompts_module_no_longer_exposes_style_dna_builders() -> None:
    from chief_editor.services.generation import prompts

    assert not hasattr(prompts, "system_style_dna_editor")
    assert not hasattr(prompts, "user_style_dna_editor")
    assert not hasattr(prompts, "SCHEMA_VOICE_BRIEF")


def test_pipeline_completes_without_voice_brief(client, session) -> None:
    """The full mock workflow must reach a draft candidate even though no
    voice_brief artifact is ever produced."""
    _seed(client)
    run = _make_run(session)
    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.status == "succeeded"
    assert run.candidate_id is not None
    artifacts = {
        a.name
        for a in session.exec(
            select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
        ).all()
    }
    assert "voice_brief" not in artifacts
    cand = session.get(PostCandidate, run.candidate_id)
    assert cand is not None
    assert cand.status == "draft"
    assert cand.tg_version  # writers still produced content from StyleProfile


def test_writer_user_prompt_uses_style_not_voice_brief() -> None:
    """Writers must take voice from style_context (StyleProfile), and a
    leftover voice_brief in the artifacts dict must be ignored."""
    from chief_editor.services.generation.prompts import user_platform_writer

    artifacts = {
        "angle": {"primary_angle": "угол"},
        "psych": {"target_emotion": "reader_recognition"},
        # A stray voice_brief must NOT be referenced by the writer prompt.
        "voice_brief": {"vocab_lane": "LEGACY_VOICE_BRIEF_MARKER"},
    }
    prompt = user_platform_writer(artifacts, "Telegram", style=None)
    assert "LEGACY_VOICE_BRIEF_MARKER" not in prompt
    assert "style_context" in prompt
    assert prompt.startswith("Действуй строго как райтер для Telegram.")


def test_finalizer_does_not_require_voice_brief(client, session) -> None:
    """finalize_candidate only needs final_brief + quality_report — never
    voice_brief. Run end-to-end and confirm the candidate exists."""
    _seed(client)
    run = _make_run(session)
    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.candidate_id is not None


# ---------------------------------------------------------------------------
# 3. Per-role temperature
# ---------------------------------------------------------------------------


def test_temperature_for_role_bands() -> None:
    # Writers
    for w in (
        "platform_writer_telegram",
        "platform_writer_threads",
        "platform_writer_reddit",
        "editor_in_chief_draft",
    ):
        assert temperature_for_role(w) == WRITER_TEMPERATURE == 0.6
    # Evaluators
    for e in ("critic_red_team", "fact_checker", "quality_judge"):
        assert temperature_for_role(e) == EVALUATOR_TEMPERATURE == 0.2
    # Analysts
    for a in (
        "research_analyst",
        "trend_strategist",
        "audience_psychology_analyst",
    ):
        assert temperature_for_role(a) == ANALYST_TEMPERATURE == 0.3
    # Unknown / non-LLM
    assert temperature_for_role("finalizer") is None


def test_step_defs_carry_role_temperature() -> None:
    for step in STEP_SEQUENCE:
        if not step.is_llm:
            assert step.role_temperature is None
            continue
        assert step.role_temperature == temperature_for_role(step.name)


class _RecordingProvider(LLMProvider):
    """Real-provider stub that records the temperature per step's schema.

    Carries a real provider name (`ollama`) so the workflow takes the
    real-provider temperature branch (StepDef.role_temperature), not the
    mock 0.0 override. Returns the mock's deterministic per-step payload so
    the workflow advances normally.
    """

    name = "ollama"

    def __init__(self) -> None:
        super().__init__()
        self.last_model = "ollama-test"
        self.by_required: dict[tuple[str, ...], float] = {}
        from chief_editor.llm.mock import MockLLMProvider

        self._mock = MockLLMProvider()

    def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        required = tuple(sorted(schema.get("required") or []))
        self.by_required[required] = temperature
        self._record_usage(input_tokens=10, output_tokens=10, model="ollama-test")
        return self._mock.complete_json(system, user, schema, temperature=0.0)

    def rewrite(self, text: str, mode: str) -> str:
        return text


def test_real_provider_receives_per_role_temperature(session, monkeypatch) -> None:
    """End-to-end: on a real provider, each LLM step is called with its
    role-band temperature. Mock is bypassed via a recording stub named
    `ollama`."""
    provider = _RecordingProvider()
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda *a, **kw: provider,
    )
    # Minimal cluster so research_analyst has input.
    cluster = TrendCluster(
        representative_text="Температурный тест",
        category="ru",
        keywords=["temp", "role"],
        score_breakdown={"recency": 0.5},
        total_score=0.5,
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)

    runs = enqueue_run(session, cluster_id=cluster.id, top_n=1, requested_by="test")
    run = runs[0]
    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.status == "succeeded", (
        f"status={run.status} err={run.error_class}:{run.error_message}"
    )

    # Map each artifact schema's required-signature to the expected band.
    def temp_for(step_name: str) -> float:
        step = get_step_by_name(step_name)
        required = tuple(sorted(step.schema["required"]))
        return provider.by_required[required]

    assert temp_for("platform_writer_telegram") == 0.6
    assert temp_for("platform_writer_reddit") == 0.6
    assert temp_for("editor_in_chief_draft") == 0.6
    assert temp_for("critic_red_team") == 0.2
    assert temp_for("fact_checker") == 0.2
    assert temp_for("quality_judge") == 0.2
    assert temp_for("research_analyst") == 0.3
    assert temp_for("trend_strategist") == 0.3
    assert temp_for("audience_psychology_analyst") == 0.3


def test_mock_provider_stays_deterministic_zero(client, session, monkeypatch) -> None:
    """The mock provider must keep receiving 0.0 from the WORKFLOW regardless
    of the role band so the deterministic test contract holds.

    Seed first, THEN attach the spy — so we only record the workflow's calls
    (the demo-seed candidate generation uses an unrelated call site with its
    own default temperature and is not part of this contract)."""
    _seed(client)

    seen: list[float] = []
    from chief_editor.llm import registry as reg

    provider = reg.get_llm_provider()
    real_complete = provider.complete_json

    def _spy(system, user, schema, *, temperature=0.7):
        seen.append(temperature)
        return real_complete(system, user, schema, temperature=temperature)

    monkeypatch.setattr(provider, "complete_json", _spy)

    run = _make_run(session)
    run_to_completion_for_tests(session, run, max_steps=20)
    assert seen, "mock provider was never called"
    assert all(t == 0.0 for t in seen), f"workflow sent non-zero temp to mock: {set(seen)}"


# ---------------------------------------------------------------------------
# 4. Synthetic mock run traverses the NEW sequence + safety invariants
# ---------------------------------------------------------------------------


def test_synthetic_run_traverses_new_sequence(client, session) -> None:
    _seed(client)
    appr_before = len(session.exec(select(ApprovalDecision)).all())
    job_before = len(session.exec(select(PublishJob)).all())

    run = _make_run(session)
    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.status == "succeeded"
    assert run.step_index == TOTAL_STEPS

    steps = list(
        session.exec(
            select(GenerationStep)
            .where(GenerationStep.run_id == run.id)
            .order_by(GenerationStep.step_index.asc())
        ).all()
    )
    assert [s.name for s in steps] == list(STEP_NAMES)
    assert all(s.status == "succeeded" for s in steps)
    # The new role names are present; the dropped one is absent.
    names = {s.name for s in steps}
    assert "fact_checker" in names
    assert "style_dna_editor" not in names

    # Safety invariants — no auto approval, no auto publish job for this run.
    cand_appr = session.exec(
        select(ApprovalDecision).where(
            ApprovalDecision.candidate_id == run.candidate_id
        )
    ).all()
    cand_jobs = session.exec(
        select(PublishJob).where(PublishJob.candidate_id == run.candidate_id)
    ).all()
    assert cand_appr == []
    assert cand_jobs == []
    assert len(session.exec(select(ApprovalDecision)).all()) == appr_before
    assert len(session.exec(select(PublishJob)).all()) == job_before


def test_quality_report_now_carries_hook_score(client, session) -> None:
    _seed(client)
    run = _make_run(session)
    run = run_to_completion_for_tests(session, run, max_steps=20)
    artifacts = {
        a.name: a.payload
        for a in session.exec(
            select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
        ).all()
    }
    qr = artifacts["quality_report"]
    assert "hook_score" in qr
    assert 0.0 <= float(qr["hook_score"]) <= 1.0


def test_wrap_input_delimits_data() -> None:
    out = wrap_input("angle", {"primary_angle": "x"})
    assert out.startswith("<angle>")
    assert out.endswith("</angle>")
    assert "primary_angle" in out
