"""Platform-scoped generation — a channel generates ONLY for its platform.

A Telegram channel (`Channel.platform == "telegram"`) must run ONLY the
Telegram writer; the Threads + Reddit writer steps are skipped WITHOUT an LLM
call (they are a pure cost + failure surface for a platform the channel never
publishes to — a Reddit writer once spun 37 min and crashed a whole run on
malformed JSON). Skipping is in-place: the step COUNT stays 11, the skipped
writers record as `succeeded` with an empty schema-valid artifact and
tokens_in/out = None.

Backward compatibility (critical): a run with no resolvable channel, or a
channel whose platform we have no dedicated writer for, runs ALL three writers
exactly as before.

All tests use the mock LLM provider — zero live network calls. The mock fills
every schema field regardless of prompt, so we detect "was this writer run?"
by spying on the LLM call (by the schema object passed), NOT by inspecting the
returned content.
"""

from __future__ import annotations

from sqlmodel import select

from chief_editor.models import (
    ApprovalDecision,
    Channel,
    GenerationArtifact,
    GenerationStep,
    PostCandidate,
    PublishJob,
    TrendCluster,
)
from chief_editor.services.channels import get_default_channel
from chief_editor.services.generation import (
    enqueue_run,
    run_to_completion_for_tests,
)
from chief_editor.services.generation import prompts as P
from chief_editor.services.generation.steps import (
    STEP_NAMES,
    WRITER_PLATFORMS,
    platform_for_step,
)

# Map a writer step's schema object (by identity) to its platform so a spy on
# complete_json can tell which writer actually called the model.
_SCHEMA_TO_PLATFORM = {
    id(P.SCHEMA_TG_POST): "telegram",
    id(P.SCHEMA_THREADS_POST): "threads",
    id(P.SCHEMA_REDDIT_POST): "reddit",
}


def _seed(client) -> None:
    client.post("/demo/seed")


def _cluster_id(session) -> str:
    cluster = session.exec(select(TrendCluster)).first()
    assert cluster is not None
    return cluster.id


def _spy_writer_calls(monkeypatch):
    """Patch the active mock provider's complete_json to record which writer
    platforms actually invoked the LLM. Returns the recording set."""
    from chief_editor.llm import registry as reg

    provider = reg.get_llm_provider()
    real = provider.complete_json
    called_platforms: set[str] = set()

    def _spy(system, user, schema, *, temperature=0.7):
        platform = _SCHEMA_TO_PLATFORM.get(id(schema))
        if platform is not None:
            called_platforms.add(platform)
        return real(system, user, schema, temperature=temperature)

    monkeypatch.setattr(provider, "complete_json", _spy)
    return called_platforms


# ---------------------------------------------------------------------------
# StepDef.platform wiring
# ---------------------------------------------------------------------------


def test_writer_steps_carry_their_platform() -> None:
    assert platform_for_step("platform_writer_telegram") == "telegram"
    assert platform_for_step("platform_writer_threads") == "threads"
    assert platform_for_step("platform_writer_reddit") == "reddit"
    assert {"telegram", "threads", "reddit"} == WRITER_PLATFORMS


def test_non_writer_steps_have_no_platform() -> None:
    for name in STEP_NAMES:
        if name.startswith("platform_writer_"):
            continue
        assert platform_for_step(name) is None, f"{name} must be platform-agnostic"


# ---------------------------------------------------------------------------
# Telegram channel skips threads + reddit writers (no LLM call)
# ---------------------------------------------------------------------------


def test_telegram_channel_skips_threads_and_reddit_writers(
    client, session, monkeypatch
) -> None:
    """The default channel is Telegram. The run must call ONLY the Telegram
    writer; Threads + Reddit writers are skipped without touching the LLM."""
    _seed(client)
    default = get_default_channel(session)
    assert default is not None and default.platform == "telegram"

    called = _spy_writer_calls(monkeypatch)

    runs = enqueue_run(
        session, cluster_id=_cluster_id(session), top_n=1, requested_by="manual"
    )
    run = runs[0]
    # enqueue stamps the default (telegram) channel.
    assert run.channel_id == default.id
    run = run_to_completion_for_tests(session, run, max_steps=20)

    assert run.status == "succeeded"
    # Only the Telegram writer ever called the model.
    assert called == {"telegram"}, f"unexpected writer LLM calls: {called}"


def test_skipped_writer_steps_are_succeeded_with_no_tokens(
    client, session
) -> None:
    """Skipped writers persist as `succeeded` (so the all-succeeded contract
    holds) but with tokens_in/out = None and an empty artifact — no LLM work."""
    _seed(client)
    runs = enqueue_run(
        session, cluster_id=_cluster_id(session), top_n=1, requested_by="manual"
    )
    run = run_to_completion_for_tests(session, runs[0], max_steps=20)
    assert run.status == "succeeded"

    steps = {
        s.name: s
        for s in session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    }
    # Step count unchanged — 11 rows, every one succeeded.
    assert len(steps) == 11
    assert all(s.status == "succeeded" for s in steps.values())

    for name in ("platform_writer_threads", "platform_writer_reddit"):
        skipped = steps[name]
        assert skipped.status == "succeeded"
        assert skipped.tokens_in is None
        assert skipped.tokens_out is None

    # The executed Telegram writer DID record tokens.
    tg = steps["platform_writer_telegram"]
    assert tg.tokens_in is not None and tg.tokens_in > 0


def test_skipped_writer_artifacts_are_empty_and_schema_valid(
    client, session
) -> None:
    """A skipped writer still writes ONE artifact (count stays 11) whose
    payload is the artifact model's empty defaults — schema-valid, carrying no
    model output and no out-of-schema marker keys."""
    from chief_editor.services.generation.artifacts import ARTIFACT_MODELS

    _seed(client)
    runs = enqueue_run(
        session, cluster_id=_cluster_id(session), top_n=1, requested_by="manual"
    )
    run = run_to_completion_for_tests(session, runs[0], max_steps=20)

    arts = {
        a.name: a
        for a in session.exec(
            select(GenerationArtifact).where(GenerationArtifact.run_id == run.id)
        ).all()
    }
    # 11 artifacts — skipped writers still produce a placeholder.
    assert len(arts) == 11
    for art_name in ("threads_post", "reddit_post"):
        art = arts[art_name]
        payload = art.payload
        allowed = set(ARTIFACT_MODELS[art_name].model_fields.keys())
        assert set(payload.keys()).issubset(allowed), (
            f"{art_name} placeholder has out-of-schema keys: "
            f"{set(payload.keys()) - allowed}"
        )
        # Empty content — there was no LLM call.
        assert payload.get("body", "") == ""
        assert "skipped" not in payload  # marker must NOT pollute the payload


# ---------------------------------------------------------------------------
# Editor + finalizer don't crash with skipped platforms
# ---------------------------------------------------------------------------


def test_editor_and_finalizer_survive_skipped_platforms(
    client, session
) -> None:
    """End-to-end on a Telegram channel: editor assembles, finalizer creates
    exactly one draft candidate, and the run succeeds — nothing crashes on the
    missing Threads/Reddit drafts."""
    _seed(client)
    runs = enqueue_run(
        session, cluster_id=_cluster_id(session), top_n=1, requested_by="manual"
    )
    run = run_to_completion_for_tests(session, runs[0], max_steps=20)

    assert run.status == "succeeded"
    assert run.candidate_id is not None
    cand = session.get(PostCandidate, run.candidate_id)
    assert cand is not None
    assert cand.status == "draft"
    assert cand.topic
    # Telegram version is real; the workflow did not crash assembling it.
    assert cand.tg_version


def test_editor_prompt_drops_skipped_platform_drafts() -> None:
    """The editor user-prompt must not ask for Threads/Reddit when the channel
    targets Telegram only: skipped drafts are dropped and their final_* fields
    are explicitly requested empty."""
    artifacts = {
        "research_brief": {"fact_bullets": ["x"]},
        "angle": {"primary_angle": "a"},
        "psych": {"target_emotion": "e"},
        "tg_post": {"body": "ТЕЛЕГРАМ_ЧЕРНОВИК", "hook": "h", "cta": "c"},
        # Skipped writers arrive as empty placeholders.
        "threads_post": {"body": "", "cta": ""},
        "reddit_post": {"title": "", "body": "", "cta": ""},
        "critic_report": {"slop_count": 0},
    }
    prompt = P.user_editor_in_chief_draft(
        artifacts, target_platforms={"telegram"}
    )
    assert "ТЕЛЕГРАМ_ЧЕРНОВИК" in prompt
    # Threads/Reddit drafts are NOT shown to the editor.
    assert "threads_draft" not in prompt
    assert "reddit_draft" not in prompt
    # final_tg is requested; final_threads/final_reddit are requested empty.
    assert "final_tg" in prompt
    assert "final_threads" in prompt and "final_reddit" in prompt
    assert "пустой строкой" in prompt


def test_editor_prompt_unscoped_keeps_all_platforms() -> None:
    """With no target set (legacy run) the editor still sees every non-empty
    draft and assembles all three platforms — the prior behaviour."""
    artifacts = {
        "tg_post": {"body": "TG"},
        "threads_post": {"body": "TH"},
        "reddit_post": {"title": "RT", "body": "RB"},
        "critic_report": {},
    }
    prompt = P.user_editor_in_chief_draft(artifacts, target_platforms=None)
    assert "telegram_draft" in prompt
    assert "threads_draft" in prompt
    assert "reddit_draft" in prompt
    assert "пустой строкой" not in prompt


# ---------------------------------------------------------------------------
# Legacy / unrecognized platform → run all three writers
# ---------------------------------------------------------------------------


def test_legacy_run_without_channel_runs_all_three_writers(
    client, session, monkeypatch
) -> None:
    """A run with channel_id=None (legacy, pre-multi-channel) has no platform
    scope — every writer runs, exactly as before. We force the legacy state by
    clearing the channel_id that enqueue stamps."""
    _seed(client)
    called = _spy_writer_calls(monkeypatch)

    runs = enqueue_run(
        session, cluster_id=_cluster_id(session), top_n=1, requested_by="manual"
    )
    run = runs[0]

    # Force the genuine legacy state: NULL channel_id, and remove the default
    # channel so `_resolve_channel` cannot fall back to it.
    run.channel_id = None
    session.add(run)
    default = get_default_channel(session)
    if default is not None:
        session.delete(default)
    session.commit()
    session.refresh(run)
    assert run.channel_id is None
    assert get_default_channel(session) is None

    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.status == "succeeded"
    # No scope → all three writers called the model.
    assert called == {"telegram", "threads", "reddit"}, (
        f"legacy run must run all writers; got {called}"
    )


def test_unrecognized_platform_channel_runs_all_three_writers(
    client, session, monkeypatch
) -> None:
    """A channel whose platform we have no dedicated writer for (e.g. a future
    'mastodon') disables scoping and runs all three writers — the documented
    unrecognized-platform fallback."""
    _seed(client)
    called = _spy_writer_calls(monkeypatch)

    # A non-default channel with an unknown platform, linked to nothing.
    channel = Channel(
        name="Future Platform",
        slug="future-platform",
        platform="mastodon",  # not in WRITER_PLATFORMS
        enabled=True,
        is_default=False,
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)

    runs = enqueue_run(
        session,
        cluster_id=_cluster_id(session),
        top_n=1,
        requested_by="manual",
        channel_id=channel.id,
    )
    run = run_to_completion_for_tests(session, runs[0], max_steps=20)
    assert run.status == "succeeded"
    assert called == {"telegram", "threads", "reddit"}, (
        f"unrecognized platform must run all writers; got {called}"
    )


# ---------------------------------------------------------------------------
# Safety invariants still hold under scoping
# ---------------------------------------------------------------------------


def test_scoped_run_creates_no_approval_or_publish_job(client, session) -> None:
    """Platform scoping must not weaken the approval-only invariant: a scoped
    Telegram run still creates exactly one draft candidate, no ApprovalDecision,
    no PublishJob."""
    _seed(client)
    appr_before = len(session.exec(select(ApprovalDecision)).all())
    job_before = len(session.exec(select(PublishJob)).all())
    cand_before = len(session.exec(select(PostCandidate)).all())

    runs = enqueue_run(
        session, cluster_id=_cluster_id(session), top_n=1, requested_by="manual"
    )
    run = run_to_completion_for_tests(session, runs[0], max_steps=20)

    assert run.status == "succeeded"
    assert run.candidate_id is not None
    assert len(session.exec(select(PostCandidate)).all()) == cand_before + 1
    assert len(session.exec(select(ApprovalDecision)).all()) == appr_before
    assert len(session.exec(select(PublishJob)).all()) == job_before


def test_failed_skip_path_leaves_no_candidate(client, session, monkeypatch) -> None:
    """Defense in depth: if a NON-skipped step fails on a scoped run, the run
    still ends `failed` with no PostCandidate — scoping changes nothing about
    the failure invariant. We fail the Telegram writer (the one step that DOES
    run) and assert no candidate is produced."""
    from chief_editor.llm import registry as reg

    _seed(client)
    cand_before = len(session.exec(select(PostCandidate)).all())

    provider = reg.get_llm_provider()
    real = provider.complete_json

    def _maybe_boom(system, user, schema, *, temperature=0.7):
        if id(schema) == id(P.SCHEMA_TG_POST):
            raise RuntimeError("telegram writer exploded")
        return real(system, user, schema, temperature=temperature)

    monkeypatch.setattr(provider, "complete_json", _maybe_boom)

    runs = enqueue_run(
        session, cluster_id=_cluster_id(session), top_n=1, requested_by="manual"
    )
    run = run_to_completion_for_tests(session, runs[0], max_steps=20)

    assert run.status == "failed"
    assert run.error_class == "RuntimeError"
    assert run.candidate_id is None
    assert len(session.exec(select(PostCandidate)).all()) == cand_before
