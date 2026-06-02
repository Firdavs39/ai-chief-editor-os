"""Phase 6 — LLM_PROVIDER_FALLBACK + token telemetry.

Phase 6 adds:
1. An optional secondary LLM provider used when the primary's full
   sequence (call + Phase-5.2 repair) fails on a NON-length validation
   error. Length overflows still surface to the operator.
2. Token usage (input + output) captured per step into
   `GenerationStep.tokens_in/out`. Cost can be computed without storing
   raw prompts or completions.

These tests lock both behaviours.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import select

from chief_editor.llm.base import LLMProvider
from chief_editor.models import (
    GenerationStep,
    TrendCluster,
)
from chief_editor.services.generation import (
    advance_one_step,
    enqueue_run,
    run_to_completion_for_tests,
)

# ---------------------------------------------------------------------------
# Scripted providers with usage telemetry
# ---------------------------------------------------------------------------


class _FailingProvider(LLMProvider):
    """Returns broken responses indefinitely. For exercising fallback paths."""

    name: str

    def __init__(self, name: str, responses: list[Any]) -> None:
        super().__init__()
        self.name = name
        self.last_model = name
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
        self._reset_usage()
        self.calls.append({"system": system, "user": user})
        if not self.responses:
            raise AssertionError(
                f"{self.name} provider out of scripted responses"
            )
        response = self.responses.pop(0)
        # Record realistic-looking usage so telemetry has values to assert
        self._record_usage(
            input_tokens=10 + len(system) // 4,
            output_tokens=20,
            model=self.name,
        )
        return response

    def rewrite(self, text: str, mode: str) -> str:
        return text


def _seed_minimal_cluster(session) -> str:
    cluster = TrendCluster(
        representative_text="Phase 6 test cluster",
        category="ru",
        keywords=["test", "phase6"],
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


# ---------------------------------------------------------------------------
# 1. Fallback fires when primary's repair also fails on non-length error
# ---------------------------------------------------------------------------


def _good_research_brief() -> dict[str, Any]:
    return {
        "editorial_rationale": "ok",
        "fact_bullets": ["a", "b", "c"],
        "source_handles": ["@s1"],
        "gaps": ["nothing"],
    }


def _broken_type_mismatch() -> dict[str, Any]:
    return {"editorial_rationale": "broken", "fact_bullets": "not-a-list"}


def test_fallback_fires_when_primary_repair_also_fails(session, monkeypatch) -> None:
    """Primary returns broken twice (original + repair both fail).
    Fallback returns valid. Step succeeds."""
    primary = _FailingProvider("primary_fake", [
        _broken_type_mismatch(),  # original
        _broken_type_mismatch(),  # repair (also broken)
    ])
    fallback = _FailingProvider("fallback_fake", [
        _good_research_brief(),   # fresh attempt → valid
    ])
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: primary,
    )
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_fallback_llm_provider",
        lambda: fallback,
    )

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)
    session.refresh(run)

    assert run.status == "running"
    assert run.step_index == 1
    # Primary called twice (original + repair), fallback called once
    assert len(primary.calls) == 2
    assert len(fallback.calls) == 1


def test_fallback_does_not_fire_on_length_overflow(session, monkeypatch) -> None:
    """Length overflows are NEVER routed to fallback — schema matches
    platform reality, content over the limit is a real content problem
    the operator must see."""
    over_limit = {
        "editorial_rationale": "x" * 2000,  # > 1500
        "fact_bullets": ["a", "b", "c"],
        "source_handles": ["@s1"],
        "gaps": ["nothing"],
    }
    primary = _FailingProvider("primary_fake", [over_limit])
    fallback = _FailingProvider("fallback_fake", [_good_research_brief()])
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: primary,
    )
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_fallback_llm_provider",
        lambda: fallback,
    )

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)
    session.refresh(run)

    assert run.status == "failed"
    # Primary called ONCE, fallback NEVER (length-only short-circuits)
    assert len(primary.calls) == 1
    assert len(fallback.calls) == 0


def test_fallback_failure_surfaces_primary_error(session, monkeypatch) -> None:
    """Primary and fallback both fail. Workflow records the PRIMARY
    failure (operator sees the original error, not the fallback's)."""
    primary = _FailingProvider("primary_fake", [
        _broken_type_mismatch(),
        _broken_type_mismatch(),
    ])
    fallback = _FailingProvider("fallback_fake", [
        _broken_type_mismatch(),  # fallback original
        _broken_type_mismatch(),  # fallback repair
    ])
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: primary,
    )
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_fallback_llm_provider",
        lambda: fallback,
    )

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)
    session.refresh(run)

    assert run.status == "failed"
    # ValidationError from primary — not from fallback
    assert run.error_class == "ValidationError"
    # Primary called 2× (original + repair). Fallback ALSO gets its own
    # validation-aware repair cycle, so 2× there too. Both providers fail
    # → primary's ValidationError surfaces.
    assert len(primary.calls) == 2
    assert len(fallback.calls) == 2


def test_no_fallback_configured_surfaces_primary_error(session, monkeypatch) -> None:
    """When `LLM_PROVIDER_FALLBACK` is empty, the workflow does not invent
    a fallback. Primary failure surfaces normally."""
    primary = _FailingProvider("primary_fake", [
        _broken_type_mismatch(),
        _broken_type_mismatch(),
    ])
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: primary,
    )
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_fallback_llm_provider",
        lambda: None,  # explicit: no fallback
    )

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)
    session.refresh(run)

    assert run.status == "failed"
    assert run.error_class == "ValidationError"
    # Primary called twice, no fallback exists
    assert len(primary.calls) == 2


# ---------------------------------------------------------------------------
# 2. Token telemetry is captured into GenerationStep
# ---------------------------------------------------------------------------


def test_token_usage_persisted_to_step(session, monkeypatch) -> None:
    """After a successful step, `GenerationStep.tokens_in/out` reflect the
    provider's reported usage."""
    provider = _FailingProvider("p", [_good_research_brief()])
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: provider,
    )
    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)
    session.refresh(run)

    step = session.exec(
        select(GenerationStep).where(GenerationStep.run_id == run.id)
    ).first()
    assert step is not None
    assert step.status == "succeeded"
    # _FailingProvider records 10+system//4 input, 20 output — both > 0
    assert step.tokens_in is not None and step.tokens_in > 0
    assert step.tokens_out == 20


def test_mock_provider_records_approximate_usage(client, session) -> None:
    """The mock provider must populate tokens_in/out so cost-tracking UI
    has values to display in dev mode.

    Platform-scoped generation (May 2026): the default channel is Telegram, so
    the Threads + Reddit writers are SKIPPED (no LLM call) and record None
    tokens like the finalizer. We assert tokens on the steps that ACTUALLY
    called the model, not on a fixed count of 10.
    """
    from chief_editor.llm import registry as llm_registry

    llm_registry.reset_provider_cache()
    client.post("/demo/seed")
    cluster = session.exec(select(TrendCluster)).first()
    runs = enqueue_run(session, cluster_id=cluster.id, top_n=1, requested_by="test")
    run = runs[0]
    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.status == "succeeded"

    steps = session.exec(
        select(GenerationStep).where(GenerationStep.run_id == run.id)
    ).all()
    no_llm_names = {
        "finalizer",
        "platform_writer_threads",  # skipped on a Telegram channel
        "platform_writer_reddit",   # skipped on a Telegram channel
    }
    executed_llm = [s for s in steps if s.name not in no_llm_names]
    no_llm_steps = [s for s in steps if s.name in no_llm_names]

    # 10 LLM roles − 2 skipped writers = 8 that called the mock provider.
    assert len(executed_llm) == 8
    for s in executed_llm:
        assert s.tokens_in is not None, f"step {s.name} missing tokens_in"
        assert s.tokens_out is not None, f"step {s.name} missing tokens_out"
        assert s.tokens_in > 0
        assert s.tokens_out > 0

    for s in no_llm_steps:
        # Finalizer (deterministic Python) + skipped writers → no LLM, no tokens.
        assert s.tokens_in is None
        assert s.tokens_out is None


def test_token_usage_reset_between_calls(session, monkeypatch) -> None:
    """Provider's `_reset_usage` runs at the START of each `complete_json`,
    so back-to-back steps each get their own counter, not accumulated.
    """
    provider = _FailingProvider("p", [
        _good_research_brief(),  # step 0
        # Step 1 (trend_strategist) requires a different shape; we'll
        # only exercise one step here. The next assertion is the
        # post-step `last_*` reset behavior.
    ])
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: provider,
    )
    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    # Before any call — usage None
    assert provider.last_input_tokens is None
    assert provider.last_output_tokens is None

    advance_one_step(session, run)

    # After step 0 — usage populated
    assert provider.last_input_tokens is not None
    assert provider.last_output_tokens == 20


# ---------------------------------------------------------------------------
# 3. Fallback + telemetry interaction
# ---------------------------------------------------------------------------


def test_fallback_telemetry_reflects_fallback_provider(session, monkeypatch) -> None:
    """When fallback fires, the persisted tokens_in/out should come from
    the FALLBACK provider, not the primary (which failed)."""
    primary = _FailingProvider("primary_fake", [
        _broken_type_mismatch(),
        _broken_type_mismatch(),
    ])
    # Fallback returns valid + records distinctive token counts
    fallback = _FailingProvider("fallback_fake", [_good_research_brief()])
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_llm_provider",
        lambda: primary,
    )
    monkeypatch.setattr(
        "chief_editor.services.generation.workflow.get_fallback_llm_provider",
        lambda: fallback,
    )

    cluster_id = _seed_minimal_cluster(session)
    runs = enqueue_run(session, cluster_id=cluster_id, top_n=1, requested_by="test")
    run = runs[0]

    advance_one_step(session, run)

    step = session.exec(
        select(GenerationStep).where(GenerationStep.run_id == run.id)
    ).first()
    assert step is not None
    assert step.status == "succeeded"
    # Fallback's reported usage (10+system//4 input, 20 output)
    assert step.tokens_out == 20
    assert step.tokens_in is not None and step.tokens_in > 0
