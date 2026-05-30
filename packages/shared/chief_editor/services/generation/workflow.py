"""Workflow engine — advances a GenerationRun one step at a time.

Public surface:
- `advance_one_step(session, run) -> GenerationRun` — production worker
  entry point (NOT wired into the worker loop in Phase 2). Idempotent in
  spirit: terminal/cancelled runs return unchanged.
- `run_to_completion_for_tests(session, run, *, max_steps=20)` — TEST-ONLY
  helper. Production API routes MUST NOT use it.

Transactional contract (the Security Lead invariant):
- A failed run leaves zero PostCandidate rows. The candidate is created
  ONLY by `finalizer.finalize_candidate` after step 10 (quality_judge)
  succeeds. Step 11 (finalizer) is the only place in this package that
  imports `PostCandidate` and only as a type hint via models.
- Cancellation is checked BEFORE each LLM call. Mid-step requests
  complete, but no subsequent step runs.
- No ApprovalDecision or PublishJob is ever created here.

The workflow uses `provider.complete_json(system, user, schema, *,
temperature=...)` exactly as the existing call sites do. Phase 2 does NOT
extend the provider signature (per QUALITY_EDITORIAL_WORKFLOW_PLAN.md §1b
and §10b). Other LLMCallOptions fields are captured for logging only.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session, select

from ...llm import get_llm_provider
from ...llm.base import LLMProvider
from ...llm.registry import get_fallback_llm_provider
from ...models import (
    Channel,
    ChannelSource,
    GenerationArtifact,
    GenerationRun,
    GenerationStep,
    RawItem,
    StyleProfile,
    SystemLog,
    TrendCluster,
    TrendSignal,
)
from ...settings import get_settings
from ...time_utils import utcnow
from ..channels import get_default_channel
from . import prompts
from .artifacts import get_run_artifacts_by_name, validate_payload
from .finalizer import finalize_candidate
from .provider_capabilities import options_for_step
from .steps import STEP_SEQUENCE, StepDef

log = logging.getLogger("chief_editor.generation.workflow")

_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_channel(session: Session, run: GenerationRun) -> Channel | None:
    """Resolve the run's channel: explicit FK → default channel → None.

    Legacy runs (`channel_id` NULL) fall back to the default channel so the
    correct style/sources are still used. Brand-new deployments with no
    default channel yet return None and the caller uses single-channel
    behaviour (default style profile, unfiltered raw items).
    """
    if run.channel_id:
        channel = session.get(Channel, run.channel_id)
        if channel is not None:
            return channel
    return get_default_channel(session)


def _load_style(session: Session, run: GenerationRun) -> StyleProfile | None:
    """Load the style profile for this run's channel.

    Resolution order:
      1. run.channel_id → Channel.style_profile_id
      2. default channel → its style_profile_id
      3. StyleProfile where name == "default" (legacy single-channel fallback)
    """
    channel = _resolve_channel(session, run)
    if channel is not None and channel.style_profile_id:
        profile = session.get(StyleProfile, channel.style_profile_id)
        if profile is not None:
            return profile
    return session.exec(
        select(StyleProfile).where(StyleProfile.name == "default")
    ).first()


def _load_cluster(session: Session, run: GenerationRun) -> TrendCluster | None:
    if not run.cluster_id:
        return None
    return session.get(TrendCluster, run.cluster_id)


def _channel_source_ids(session: Session, run: GenerationRun) -> set[str] | None:
    """Source ids linked to the run's channel, or None for no filtering.

    Returns None when the run has no resolvable channel (legacy/NULL with no
    default) — callers then keep the unfiltered single-channel behaviour.
    """
    channel = _resolve_channel(session, run)
    if channel is None:
        return None
    return set(
        session.exec(
            select(ChannelSource.source_id).where(
                ChannelSource.channel_id == channel.id
            )
        ).all()
    )


def _load_raw_items(
    session: Session,
    cluster: TrendCluster | None,
    *,
    run: GenerationRun,
    limit: int = 5,
) -> list[RawItem]:
    """Raw items backing the cluster, restricted to the channel's sources.

    Filtering by the channel's source pool prevents another channel's context
    from leaking into this channel's prompts. When the run has no resolvable
    channel (legacy NULL with no default), no filter is applied and the prior
    single-channel behaviour is preserved.
    """
    if cluster is None:
        return []

    stmt = (
        select(RawItem)
        .join(TrendSignal, TrendSignal.raw_item_id == RawItem.id)
        .where(TrendSignal.cluster_id == cluster.id)
    )
    source_ids = _channel_source_ids(session, run)
    if source_ids is not None:
        if not source_ids:
            # Channel exists but has no linked sources → nothing to feed the
            # prompt from this channel's pool. Return empty rather than leak
            # the whole cluster's items.
            return []
        stmt = stmt.where(RawItem.source_id.in_(source_ids))  # type: ignore[attr-defined]

    return list(session.exec(stmt.limit(limit)).all())


def _model_name_for(provider_name: str) -> str:
    s = get_settings()
    if provider_name == "anthropic":
        return s.anthropic_model
    if provider_name == "openai":
        return s.openai_model
    if provider_name == "ollama":
        return s.ollama_model
    return ""


def _audit_run_log(
    session: Session, event: str, *, run: GenerationRun, **extra: Any
) -> None:
    """Whitelisted SystemLog write. Allowed keys mirror the secrets router's
    `_audit`: run_id, status, step_count, duration_ms, error_class.

    Anything else is silently dropped. The vault secret-substring sweep
    tests cover this surface; this helper is the canonical entry point.
    """
    allowed = {"run_id", "status", "step_count", "duration_ms", "error_class"}
    data: dict[str, Any] = {"run_id": run.id, "status": run.status}
    data.update({k: v for k, v in extra.items() if k in allowed})
    session.add(SystemLog(level="info", event=event, message="", data=data))
    session.commit()


# ---------------------------------------------------------------------------
# User-prompt dispatch (different signature per step)
# ---------------------------------------------------------------------------


def _build_user_prompt(
    step_def: StepDef,
    *,
    cluster: TrendCluster | None,
    raw_items: list[RawItem],
    artifacts: dict[str, dict],
    style: StyleProfile | None,
) -> str:
    builder = step_def.user_builder_name
    if builder == "research_analyst":
        return prompts.user_research_analyst(cluster, raw_items)
    if builder == "trend_strategist":
        return prompts.user_trend_strategist(cluster, artifacts)
    if builder == "audience_psychology":
        return prompts.user_audience_psychology(artifacts, style)
    if builder == "style_dna_editor":
        return prompts.user_style_dna_editor(artifacts, style)
    if builder == "platform_writer_telegram":
        return prompts.user_platform_writer(artifacts, "Telegram", style=style)
    if builder == "platform_writer_threads":
        return prompts.user_platform_writer(artifacts, "Threads", style=style)
    if builder == "platform_writer_reddit":
        return prompts.user_platform_writer(artifacts, "Reddit", style=style)
    if builder == "critic_red_team":
        return prompts.user_critic_red_team(artifacts)
    if builder == "editor_in_chief_draft":
        return prompts.user_editor_in_chief_draft(artifacts)
    if builder == "quality_judge":
        return prompts.user_quality_judge(artifacts)
    raise RuntimeError(f"unknown user_builder_name '{builder}'")


# ---------------------------------------------------------------------------
# Validation-aware repair (Phase 5.2)
# ---------------------------------------------------------------------------


def _is_length_only_error(exc: ValidationError) -> bool:
    """True iff every error in the ValidationError is a length overflow.

    After Phase 5.2 raised the schema limits to platform-real values, length
    overflows should be rare. When they DO happen the schema is acting as
    designed (refuses to silently truncate creative content), so we do NOT
    retry — we surface the error and let the operator decide.

    Non-length errors (enum mismatch, missing required field, score out of
    range) are model-output bugs that a clarifying retry can usually fix.
    """
    errors = exc.errors()
    if not errors:
        return False
    length_types = {"string_too_long", "string_too_short", "too_long", "too_short"}
    return all(e.get("type") in length_types for e in errors)


def _summarize_validation_errors(exc: ValidationError) -> str:
    """Compact, log-safe summary of a ValidationError.

    No raw payload text. No prompt content. Field names + error types + the
    pydantic message line (already free of secret values). Capped at 400
    chars so it fits in safe storage and logs.
    """
    parts: list[str] = []
    for e in exc.errors()[:6]:
        loc = ".".join(str(x) for x in e.get("loc", ())) or "?"
        t = e.get("type", "?")
        msg = (e.get("msg") or "").splitlines()[0][:80]
        parts.append(f"{loc}:{t}:{msg}")
    return " | ".join(parts)[:400]


def _build_repair_prompt(
    step_def: StepDef, original_payload: dict[str, Any], exc: ValidationError
) -> str:
    """Build a repair user-prompt asking the model to correct its JSON.

    Contains:
    - step name
    - structured list of allowed schema field names (from the step's schema)
    - compact validation-error summary (NO raw model text outside the
      original payload itself, which the model produced and is free to see)
    - the original payload, dumped as JSON
    - the safety footer
    """
    schema_props = (step_def.schema or {}).get("properties", {})
    allowed = list(schema_props.keys())
    err_summary = _summarize_validation_errors(exc)
    original_json = json.dumps(original_payload, ensure_ascii=False)[:4000]
    return (
        f"Предыдущий JSON для шага `{step_def.name}` не прошёл валидацию.\n"
        f"Ошибки: {err_summary}\n"
        f"Разрешённые поля: {allowed}\n"
        f"Твой предыдущий ответ:\n{original_json}\n\n"
        "Верни ИСПРАВЛЕННЫЙ JSON, который проходит схему. Только JSON, "
        "никаких комментариев или ```-блоков. "
        + prompts.SAFETY_FOOTER
    )


def _merge_deterministic_flags_into_critic(
    payload: dict[str, Any], artifacts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Phase Q v5 (post-R3 supervisor pattern): after the LLM critic
    returns its judgement, Python re-runs the deterministic AI-tells
    detector on the same drafts and MERGES findings into the payload.

    This is defense-in-depth — Sierra's "Jiminy Cricket" output-supervisor
    pattern. The LLM critic SHOULD surface deterministic flags itself
    (the user prompt instructs it to), but even if it forgets or
    soft-pedals, this merge guarantees floor-quality flags reach the
    operator.

    Mutation contract:
    - slop_count incremented by number of NEW flag categories detected
      (capped at 9, since hook_grade caps the relevant zone).
    - length_issues list extended with deterministic-only flags (truncated
      to the schema's 3-item max).
    - factual_concerns is NOT mutated — those are editorial judgements,
      not mechanical AI-tells.
    """
    from .ai_tells import analyze_drafts

    tg = artifacts.get("tg_post", {})
    th = artifacts.get("threads_post", {})
    rd = artifacts.get("reddit_post", {})

    reports = analyze_drafts(
        tg_body=str(tg.get("body", "")),
        threads_body=str(th.get("body", "")),
        reddit_body=str(rd.get("body", "")),
    )

    # Collect all flag strings across the three platforms, prefixed by platform.
    new_flags: list[str] = []
    new_slop = 0
    for platform, report in reports.items():
        new_slop += report.slop_count
        for flag in report.flags:
            new_flags.append(f"[{platform}] {flag}")

    # Mutate length_issues — extend with deterministic flags the LLM may
    # have missed. Cap at schema's max (3 items).
    existing = list(payload.get("length_issues") or [])
    existing_set = set(existing)
    for f in new_flags:
        if f not in existing_set and len(existing) < 3:
            existing.append(f)
            existing_set.add(f)
    payload["length_issues"] = existing

    # Update slop_count — take the MAX of LLM's value and detector's
    # count. The LLM may add its own slop observations on top of
    # mechanical AI-tells, so we don't simply overwrite.
    llm_slop = int(payload.get("slop_count") or 0)
    payload["slop_count"] = max(llm_slop, new_slop)

    return payload


def _log_artifact_lengths(step_name: str, payload: dict[str, Any]) -> None:
    """Observability hook (Phase 5.2): record per-field string lengths.

    Lengths only — never the values themselves. Operators can grep logs by
    `generation.step.lengths` to see field-length distribution over time and
    spot drift (e.g. Kimi suddenly writing 1400-char rationales).
    """
    lengths = {
        k: len(v) for k, v in payload.items() if isinstance(v, str)
    }
    log.info(
        "generation.step.lengths step=%s lengths=%s",
        step_name,
        lengths,
    )


# ---------------------------------------------------------------------------
# Step executors
# ---------------------------------------------------------------------------


def _call_provider_with_repair(
    provider: LLMProvider,
    *,
    step_def: StepDef,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
) -> dict[str, Any]:
    """Run one LLM step on the given provider with validation-aware repair.

    Single attempt model:
    1. complete_json → raw
    2. if not dict → ValueError (raised to caller — fallback may try, repair will not)
    3. validate_payload(raw) → if OK, return validated
    4. if ValidationError is length-only → re-raise (no repair, no fallback)
    5. otherwise → repair-prompt → complete_json → validate → return-or-raise

    The caller (Phase 6 wrapper) decides whether to retry the WHOLE thing
    on a configured fallback provider.
    """
    raw_payload = provider.complete_json(
        system=system_prompt,
        user=user_prompt,
        schema=step_def.schema,  # type: ignore[arg-type]
        temperature=temperature,
    )
    if not isinstance(raw_payload, dict):
        raise ValueError(
            f"provider returned non-dict payload for {step_def.name}: "
            f"{type(raw_payload).__name__}"
        )

    try:
        validated = validate_payload(step_def.artifact_name, raw_payload)
        _log_artifact_lengths(step_def.name, validated)
        return validated
    except ValidationError as exc:
        if _is_length_only_error(exc):
            log.info(
                "generation.step.length_overflow step=%s provider=%s errors=%s",
                step_def.name,
                provider.name,
                _summarize_validation_errors(exc),
            )
            raise

        log.info(
            "generation.step.repair_attempted step=%s provider=%s errors=%s",
            step_def.name,
            provider.name,
            _summarize_validation_errors(exc),
        )
        repair_prompt = _build_repair_prompt(step_def, raw_payload, exc)
        repaired = provider.complete_json(
            system=system_prompt,
            user=repair_prompt,
            schema=step_def.schema,  # type: ignore[arg-type]
            temperature=min(temperature, 0.3),
        )
        if not isinstance(repaired, dict):
            raise ValueError(
                f"repair returned non-dict payload for {step_def.name}: "
                f"{type(repaired).__name__}"
            ) from exc
        validated = validate_payload(step_def.artifact_name, repaired)
        log.info(
            "generation.step.repair_succeeded step=%s provider=%s",
            step_def.name,
            provider.name,
        )
        _log_artifact_lengths(step_def.name, validated)
        return validated


def _execute_llm_step(
    session: Session, run: GenerationRun, step_def: StepDef
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one LLM step. Returns (validated_payload, usage_dict).

    `usage_dict` keys: `tokens_in: int | None`, `tokens_out: int | None`,
    `model: str | None`, `used_fallback: bool`. The workflow persists
    `tokens_in`/`tokens_out` into `GenerationStep.tokens_in/out` so cost
    can be computed without storing raw prompts/responses.

    Phase 5.2 added validation-aware repair (one retry on non-length
    ValidationError with a structured repair prompt). Phase 6 adds an
    optional fallback provider: if `LLM_PROVIDER_FALLBACK` is set and the
    primary's full sequence (call + repair) fails on a NON-length error,
    the workflow makes ONE fresh attempt on the fallback provider for the
    same step. If the fallback also fails, the ORIGINAL exception is
    re-raised — operators see the primary's error first.

    Length overflows are NEVER routed to fallback. The schema now matches
    platform reality; an overflow is a genuine content problem the operator
    must see, not a parsing artifact that a different provider can paper
    over.
    """
    primary = get_llm_provider()
    style = _load_style(session, run)
    cluster = _load_cluster(session, run)
    raw_items = _load_raw_items(session, cluster, run=run, limit=5)
    artifacts = get_run_artifacts_by_name(session, run)

    if step_def.system_builder is None or step_def.schema is None:
        raise RuntimeError(
            f"step {step_def.name} marked is_llm but missing prompt/schema"
        )
    system_prompt = step_def.system_builder(style)
    user_prompt = _build_user_prompt(
        step_def,
        cluster=cluster,
        raw_items=raw_items,
        artifacts=artifacts,
        style=style,
    )
    options = options_for_step(
        primary.name, step_def.name, is_judge=step_def.is_judge
    )
    temperature = (
        options.temperature if options.temperature is not None else 0.7
    )

    def _usage_for(provider: LLMProvider, used_fallback: bool) -> dict[str, Any]:
        return {
            "tokens_in": provider.last_input_tokens,
            "tokens_out": provider.last_output_tokens,
            "model": provider.last_model,
            "used_fallback": used_fallback,
        }

    try:
        payload = _call_provider_with_repair(
            primary,
            step_def=step_def,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
        # Phase Q v5: critic step gets a deterministic flag-merge on top
        # of the LLM's editorial judgment. Sierra-style output-supervisor.
        if step_def.name == "critic_red_team":
            payload = _merge_deterministic_flags_into_critic(payload, artifacts)
        return payload, _usage_for(primary, used_fallback=False)
    except ValidationError as primary_exc:
        # Length-only failures must NEVER fall back. The schema is correct;
        # the model produced content that exceeds a platform limit. The
        # operator sees the failure.
        if _is_length_only_error(primary_exc):
            raise

        fallback = get_fallback_llm_provider()
        if fallback is None:
            # No fallback configured — surface the primary's error.
            raise

        log.info(
            "generation.step.fallback_attempted step=%s primary=%s fallback=%s",
            step_def.name,
            primary.name,
            fallback.name,
        )
        try:
            payload = _call_provider_with_repair(
                fallback,
                step_def=step_def,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
            )
            log.info(
                "generation.step.fallback_succeeded step=%s fallback=%s",
                step_def.name,
                fallback.name,
            )
            if step_def.name == "critic_red_team":
                payload = _merge_deterministic_flags_into_critic(payload, artifacts)
            return payload, _usage_for(fallback, used_fallback=True)
        except Exception as fb_exc:  # noqa: BLE001 — surface the original
            log.info(
                "generation.step.fallback_failed step=%s fallback=%s err=%s",
                step_def.name,
                fallback.name,
                type(fb_exc).__name__,
            )
            # Re-raise the PRIMARY exception so the run records the
            # original failure mode; the fallback's failure is in logs.
            raise primary_exc from fb_exc


def _execute_finalizer_step(session: Session, run: GenerationRun) -> dict[str, Any]:
    """Backend assembly step. NO LLM call."""
    return finalize_candidate(session, run)


# ---------------------------------------------------------------------------
# Main advance entry point
# ---------------------------------------------------------------------------


def advance_one_step(session: Session, run: GenerationRun) -> GenerationRun:
    """Advance a GenerationRun by exactly one step. Commits per step.

    Behavior:
    - If `run.status` is terminal/cancelled: return immediately.
    - If `run.status == "queued"`: flip to "running", snapshot provider/model.
    - Create the next GenerationStep row with status="running".
    - Re-check `run.status` after the step row commit: a cancellation that
      landed between picks short-circuits BEFORE any LLM call.
    - Execute the step (LLM or finalizer).
    - On success: persist artifact, mark step succeeded, advance step_index.
      If this was the last step, mark run succeeded.
    - On any exception: mark step failed, mark run failed, truncate
      error_message to 240 chars. NO PostCandidate row is created.
    """
    session.refresh(run)
    if run.status in _TERMINAL_STATUSES:
        return run

    # Queued → running transition (one-time per run).
    if run.status == "queued":
        provider = get_llm_provider()
        run.status = "running"
        run.started_at = utcnow()
        run.provider = provider.name
        run.model = _model_name_for(provider.name)
        run.updated_at = utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        _audit_run_log(
            session,
            "generation.run.started",
            run=run,
            step_count=len(STEP_SEQUENCE),
        )

    idx = run.step_index
    if idx >= len(STEP_SEQUENCE):
        run.status = "succeeded"
        run.finished_at = utcnow()
        run.updated_at = utcnow()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    step_def = STEP_SEQUENCE[idx]
    started_at = utcnow()

    step = GenerationStep(
        run_id=run.id,
        step_index=idx,
        name=step_def.name,
        status="running",
        started_at=started_at,
    )
    session.add(step)
    session.commit()
    session.refresh(step)

    # Re-check cancellation — if a cancel came in between picks, short-circuit
    # BEFORE any LLM call. This is the cancellation hard rule.
    session.refresh(run)
    if run.status == "cancelled":
        step.status = "cancelled"
        step.finished_at = utcnow()
        step.updated_at = utcnow()
        session.add(step)
        session.commit()
        return run

    try:
        if step_def.is_llm:
            payload, usage = _execute_llm_step(session, run, step_def)
        else:
            payload = _execute_finalizer_step(session, run)
            usage = {
                "tokens_in": None,
                "tokens_out": None,
                "model": None,
                "used_fallback": False,
            }

        artifact = GenerationArtifact(
            run_id=run.id,
            step_id=step.id,
            name=step_def.artifact_name,
            schema_version="v1",
            payload=payload,
        )
        session.add(artifact)

        finished_at = utcnow()
        step.status = "succeeded"
        step.finished_at = finished_at
        step.duration_ms = int(
            (finished_at - started_at).total_seconds() * 1000
        )
        # Phase 6: persist token usage so cost can be computed without
        # storing raw prompts/completions. None values stay None.
        step.tokens_in = usage["tokens_in"]
        step.tokens_out = usage["tokens_out"]
        step.updated_at = finished_at

        run.step_index = idx + 1
        run.current_step = step_def.name
        run.updated_at = finished_at

        # Final step → mark run succeeded.
        if run.step_index >= len(STEP_SEQUENCE):
            run.status = "succeeded"
            run.finished_at = finished_at

        session.add(step)
        session.add(run)
        session.commit()
        session.refresh(run)

        if run.status == "succeeded":
            _audit_run_log(
                session,
                "generation.run.succeeded",
                run=run,
                step_count=run.step_index,
            )
        return run

    except Exception as exc:  # noqa: BLE001 — one terminal failure path
        msg = str(exc)[:240]
        error_class = type(exc).__name__

        # Discard ANY uncommitted state staged by this step. Critical for the
        # finalizer step: finalize_candidate stages a PostCandidate and a
        # run.candidate_id update without committing; if a downstream
        # operation in this try-block then fails, the rollback prevents an
        # orphan PostCandidate from persisting. For LLM steps this is a
        # no-op (provider failures leave nothing staged on the session).
        session.rollback()

        finished_at = utcnow()

        # The step row and run row were committed earlier (with status
        # "running"), so they exist in the DB. Re-fetch them through the
        # session so the failure-state update happens on fresh ORM objects.
        step_db = session.get(GenerationStep, step.id)
        if step_db is not None:
            step_db.status = "failed"
            step_db.finished_at = finished_at
            step_db.error_class = error_class
            step_db.error_message = msg
            if started_at:
                step_db.duration_ms = int(
                    (finished_at - started_at).total_seconds() * 1000
                )
            step_db.updated_at = finished_at
            session.add(step_db)

        run_db = session.get(GenerationRun, run.id) or run
        run_db.status = "failed"
        run_db.error_class = error_class
        run_db.error_message = msg
        run_db.finished_at = finished_at
        run_db.updated_at = finished_at
        # Defensive: ensure candidate_id stays None on failure even if some
        # caller mutated the in-memory object before the exception fired.
        run_db.candidate_id = None
        session.add(run_db)
        session.commit()
        session.refresh(run_db)

        log.warning(
            "generation.run.failed run_id=%s step=%s error_class=%s",
            run_db.id,
            step_def.name,
            error_class,
        )
        _audit_run_log(
            session,
            "generation.run.failed",
            run=run_db,
            error_class=error_class,
        )
        return run_db


# ---------------------------------------------------------------------------
# TEST-ONLY helper
# ---------------------------------------------------------------------------


def run_to_completion_for_tests(
    session: Session, run: GenerationRun, *, max_steps: int = 20
) -> GenerationRun:
    """TEST-ONLY: repeatedly call `advance_one_step` until terminal.

    DO NOT USE THIS FROM PRODUCTION API ROUTES OR WORKER LOOPS. The production
    worker loop (Phase 3+) calls `advance_one_step` once per tick and relies
    on its own scheduling so concurrency caps and cancellations work. This
    helper exists so end-to-end tests stay deterministic.
    """
    for _ in range(max_steps):
        session.refresh(run)
        if run.status in _TERMINAL_STATUSES:
            return run
        advance_one_step(session, run)
    session.refresh(run)
    if run.status not in _TERMINAL_STATUSES:
        raise RuntimeError(
            f"workflow did not terminate in {max_steps} steps "
            f"(status={run.status}, step_index={run.step_index})"
        )
    return run


__all__ = [
    "advance_one_step",
    "run_to_completion_for_tests",
]
