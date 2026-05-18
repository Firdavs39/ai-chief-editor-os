"""POST /brief/generate — backward-compatible entry into candidate generation.

Two response shapes, selected by runtime mode (the choice is intentional —
mock-mode shape MUST remain identical for the pinned test suite):

- **Mock mode** (`MOCK_MODE=true` OR `LLM_PROVIDER=mock`) — synchronous.
  Returns `list[CandidateOut]` exactly as before. The full mock pipeline
  (`generate_for_cluster`) runs in-process and the test suite at
  `tests/test_brief_generate_safety.py` continues to assert candidates land
  with `status="draft"` and no `ApprovalDecision` / `PublishJob` rows are
  created.

- **Real-provider mode** (any non-mock provider) — async. Enqueues one or
  more `GenerationRun` rows via `services.generation.enqueue_run` and
  returns HTTP 202 with `{run_ids, status: "queued"}`. **No LLM call is
  made on the request thread.** The worker (Phase 2+) advances the runs.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from chief_editor.models import TrendCluster
from chief_editor.schemas import CandidateOut
from chief_editor.services.candidate import generate_for_cluster
from chief_editor.services.generation import enqueue_run
from chief_editor.settings import get_settings

from ..deps import get_session

router = APIRouter(prefix="/brief", tags=["briefs"])


class BriefGenerateRequest(BaseModel):
    cluster_id: str | None = None
    top_n: int = 3


def _is_mock_mode() -> bool:
    s = get_settings()
    return bool(s.mock_mode) or s.llm_provider == "mock"


@router.post("/generate")
def generate(
    payload: BriefGenerateRequest,
    session: Session = Depends(get_session),
) -> Any:
    if _is_mock_mode():
        # Synchronous legacy path — bare list[CandidateOut] response shape
        # preserved exactly for callers and tests/test_brief_generate_safety.py.
        if payload.cluster_id:
            cluster = session.get(TrendCluster, payload.cluster_id)
            clusters = [cluster] if cluster else []
        else:
            clusters = list(
                session.exec(
                    select(TrendCluster)
                    .order_by(TrendCluster.total_score.desc())
                    .limit(payload.top_n)
                ).all()
            )

        out: list[CandidateOut] = []
        for cluster in clusters:
            cand = generate_for_cluster(session, cluster)
            out.append(CandidateOut(**cand.model_dump()))
        return [c.model_dump(mode="json") for c in out]

    # Real-provider mode: enqueue runs, return 202. No LLM call here.
    runs = enqueue_run(
        session,
        cluster_id=payload.cluster_id,
        top_n=payload.top_n,
        requested_by="api",
    )
    return JSONResponse(
        status_code=202,
        content={
            "run_ids": [r.id for r in runs],
            "status": "queued",
        },
    )
