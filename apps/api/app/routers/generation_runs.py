"""Quality Editorial Workflow — `/generation-runs` router.

ALL endpoints are gated by `require_admin_token` from `apps/api/app/deps.py`.
Same trust zone and same dependency the vault router uses. Rationale:
generation runs trigger real LLM cost and the artifacts they produce are
private editorial work; in the current alpha/live/public-tunnel context this
must not be open to anonymous callers.

Phase 1 only:
- POST creates queued `GenerationRun` rows. No worker execution.
- GET endpoints return rows. Steps and artifacts will populate once the
  worker is wired (Phase 2/3).
- Cancel marks a queued run as `cancelled`; on a `running` run the worker
  will honor the flag on the next tick (Phase 3).
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from chief_editor.models import (
    GenerationArtifact,
    GenerationRun,
    GenerationStep,
    SystemLog,
)
from chief_editor.services.generation import enqueue_run
from chief_editor.time_utils import utcnow

from ..deps import get_session, require_admin_token

log = logging.getLogger("chief_editor.generation_runs")

router = APIRouter(
    prefix="/generation-runs",
    tags=["generation-runs"],
    dependencies=[Depends(require_admin_token)],
)


# ---------------------------------------------------------------------------
# Pydantic response/request models — never carry plaintext secrets or
# private chain-of-thought. Artifacts surface only their canonical payload.
# ---------------------------------------------------------------------------


class GenerationRunCreate(BaseModel):
    cluster_id: str | None = None
    top_n: int = 1
    requested_by: str = "api"


class GenerationRunOut(BaseModel):
    id: str
    cluster_id: str | None
    requested_by: str
    status: str
    current_step: str
    step_index: int
    total_steps: int
    candidate_id: str | None
    error_class: str
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime


class GenerationRunsResponse(BaseModel):
    """Discriminated 202 response for `POST /generation-runs`."""

    runs: list[GenerationRunOut] = Field(default_factory=list)
    status: str = "queued"


class GenerationStepOut(BaseModel):
    id: str
    run_id: str
    step_index: int
    name: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    tokens_in: int | None
    tokens_out: int | None
    error_class: str
    error_message: str
    created_at: datetime
    updated_at: datetime


class GenerationArtifactOut(BaseModel):
    id: str
    run_id: str
    step_id: str
    name: str
    schema_version: str
    payload: dict
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def _serialize_run(run: GenerationRun) -> GenerationRunOut:
    return GenerationRunOut(
        id=run.id,
        cluster_id=run.cluster_id,
        requested_by=run.requested_by,
        status=run.status,
        current_step=run.current_step,
        step_index=run.step_index,
        total_steps=run.total_steps,
        candidate_id=run.candidate_id,
        error_class=run.error_class,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
        provider=run.provider,
        model=run.model,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _audit(session: Session, event: str, **data: object) -> None:
    """Whitelisted SystemLog write for generation events.

    Allowed keys: run_id, status, step_count, duration_ms, error_class.
    Anything else is silently dropped — this is the contract the Security
    Lead audit enforces.
    """
    allowed = {"run_id", "status", "step_count", "duration_ms", "error_class"}
    safe = {k: v for k, v in data.items() if k in allowed}
    session.add(SystemLog(level="info", event=event, message="", data=safe))
    session.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=GenerationRunsResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
)
def create_runs(
    body: GenerationRunCreate,
    session: Session = Depends(get_session),
) -> GenerationRunsResponse:
    """Enqueue one or more generation runs. Returns HTTP 202.

    The worker (Phase 2+) will pick them up. Phase 1 only persists the rows.
    """
    runs = enqueue_run(
        session,
        cluster_id=body.cluster_id,
        top_n=body.top_n,
        requested_by=body.requested_by,
    )
    if not runs:
        # No clusters available at all — return an empty list at 202 rather
        # than 404 to keep the contract async.
        return GenerationRunsResponse(runs=[], status="queued")
    return GenerationRunsResponse(
        runs=[_serialize_run(r) for r in runs],
        status="queued",
    )


@router.get("", response_model=list[GenerationRunOut])
def list_runs(
    status: str | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[GenerationRunOut]:
    stmt = select(GenerationRun)
    if status:
        stmt = stmt.where(GenerationRun.status == status)
    stmt = stmt.order_by(GenerationRun.created_at.desc()).limit(max(1, min(int(limit or 50), 200)))
    rows = list(session.exec(stmt).all())
    return [_serialize_run(r) for r in rows]


@router.get("/{run_id}", response_model=GenerationRunOut)
def get_run(run_id: str, session: Session = Depends(get_session)) -> GenerationRunOut:
    run = session.get(GenerationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    return _serialize_run(run)


@router.get("/{run_id}/steps", response_model=list[GenerationStepOut])
def list_steps(
    run_id: str, session: Session = Depends(get_session)
) -> list[GenerationStepOut]:
    if session.get(GenerationRun, run_id) is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    rows = list(
        session.exec(
            select(GenerationStep)
            .where(GenerationStep.run_id == run_id)
            .order_by(GenerationStep.step_index.asc())
        ).all()
    )
    return [
        GenerationStepOut(
            id=s.id,
            run_id=s.run_id,
            step_index=s.step_index,
            name=s.name,
            status=s.status,
            started_at=s.started_at,
            finished_at=s.finished_at,
            duration_ms=s.duration_ms,
            tokens_in=s.tokens_in,
            tokens_out=s.tokens_out,
            error_class=s.error_class,
            error_message=s.error_message,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in rows
    ]


@router.get("/{run_id}/artifacts", response_model=list[GenerationArtifactOut])
def list_artifacts(
    run_id: str, session: Session = Depends(get_session)
) -> list[GenerationArtifactOut]:
    if session.get(GenerationRun, run_id) is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    rows = list(
        session.exec(
            select(GenerationArtifact)
            .where(GenerationArtifact.run_id == run_id)
            .order_by(GenerationArtifact.created_at.asc())
        ).all()
    )
    return [
        GenerationArtifactOut(
            id=a.id,
            run_id=a.run_id,
            step_id=a.step_id,
            name=a.name,
            schema_version=a.schema_version,
            payload=a.payload or {},
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in rows
    ]


@router.post("/{run_id}/cancel", response_model=GenerationRunOut)
def cancel_run(
    run_id: str, session: Session = Depends(get_session)
) -> GenerationRunOut:
    run = session.get(GenerationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run_not_found")
    if run.status in _TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="run_already_terminal")
    run.status = "cancelled"
    run.finished_at = utcnow()
    run.updated_at = utcnow()
    session.add(run)
    session.commit()
    session.refresh(run)
    _audit(session, "generation.run.cancelled", run_id=run.id, status=run.status)
    return _serialize_run(run)
