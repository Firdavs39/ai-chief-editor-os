"""HTTP-level tests for the `/generation-runs` router (Phase 1).

Every endpoint requires `X-Admin-Token`. The Phase 1 implementation:
- POST → 202 + list of queued runs (no LLM call).
- GET endpoints return rows.
- Cancel flips queued/running runs to cancelled; 409 on terminal.
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from chief_editor.models import (
    ApprovalDecision,
    GenerationArtifact,
    GenerationRun,
    GenerationStep,
    PostCandidate,
    PublishJob,
)
from chief_editor.settings import get_settings

PROD_TOKEN = "test-admin-token-generation-runs"
HDR = {"X-Admin-Token": PROD_TOKEN}


@pytest.fixture()
def admin_client(client, monkeypatch):
    """Client with ADMIN_TOKEN set so write/test endpoints are unlocked."""
    monkeypatch.setenv("ADMIN_TOKEN", PROD_TOKEN)
    get_settings.cache_clear()
    yield client


def _seed_clusters(client) -> None:
    client.post("/demo/seed")


# ---------------------------------------------------------------------------
# Auth: every endpoint rejects missing/bad token.
# ---------------------------------------------------------------------------


def test_post_without_token_returns_401(admin_client) -> None:
    r = admin_client.post("/generation-runs", json={"top_n": 1})
    assert r.status_code == 401


def test_get_list_without_token_returns_401(admin_client) -> None:
    r = admin_client.get("/generation-runs")
    assert r.status_code == 401


def test_get_one_without_token_returns_401(admin_client) -> None:
    r = admin_client.get("/generation-runs/some-id")
    assert r.status_code == 401


def test_get_steps_without_token_returns_401(admin_client) -> None:
    r = admin_client.get("/generation-runs/some-id/steps")
    assert r.status_code == 401


def test_get_artifacts_without_token_returns_401(admin_client) -> None:
    r = admin_client.get("/generation-runs/some-id/artifacts")
    assert r.status_code == 401


def test_cancel_without_token_returns_401(admin_client) -> None:
    r = admin_client.post("/generation-runs/some-id/cancel")
    assert r.status_code == 401


def test_wrong_token_returns_401(admin_client) -> None:
    r = admin_client.post(
        "/generation-runs",
        json={"top_n": 1},
        headers={"X-Admin-Token": "WRONG-TOKEN"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST creates queued runs (no LLM call, no side effects).
# ---------------------------------------------------------------------------


def test_post_creates_queued_runs_202(admin_client, session) -> None:
    _seed_clusters(admin_client)
    r = admin_client.post("/generation-runs", json={"top_n": 2}, headers=HDR)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert isinstance(body["runs"], list)
    assert len(body["runs"]) >= 1
    from chief_editor.services.generation import TOTAL_STEPS

    for run in body["runs"]:
        assert run["status"] == "queued"
        assert run["step_index"] == 0
        # Phase 2: TOTAL_STEPS is 11 (10 LLM steps + finalizer).
        assert run["total_steps"] == TOTAL_STEPS
        assert run["candidate_id"] is None


def test_post_with_specific_cluster_id_creates_one_run(admin_client, session) -> None:
    _seed_clusters(admin_client)
    # Pull a real cluster id from /trends.
    trends = admin_client.get("/trends").json()
    assert trends, "demo seed should produce at least one trend"
    cid = trends[0]["id"]

    r = admin_client.post(
        "/generation-runs",
        json={"cluster_id": cid, "top_n": 5},  # top_n ignored when cluster_id set
        headers=HDR,
    )
    assert r.status_code == 202
    runs = r.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["cluster_id"] == cid
    assert runs[0]["status"] == "queued"


def test_post_does_not_create_post_candidate_approval_or_job(admin_client, session) -> None:
    _seed_clusters(admin_client)
    cand_before = len(session.exec(select(PostCandidate)).all())
    appr_before = len(session.exec(select(ApprovalDecision)).all())
    job_before = len(session.exec(select(PublishJob)).all())

    admin_client.post("/generation-runs", json={"top_n": 2}, headers=HDR)

    assert len(session.exec(select(PostCandidate)).all()) == cand_before
    assert len(session.exec(select(ApprovalDecision)).all()) == appr_before
    assert len(session.exec(select(PublishJob)).all()) == job_before


# ---------------------------------------------------------------------------
# GET endpoints.
# ---------------------------------------------------------------------------


def test_get_list_returns_runs(admin_client) -> None:
    _seed_clusters(admin_client)
    admin_client.post("/generation-runs", json={"top_n": 1}, headers=HDR)
    r = admin_client.get("/generation-runs", headers=HDR)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1


def test_get_by_id_returns_run(admin_client) -> None:
    _seed_clusters(admin_client)
    created = admin_client.post(
        "/generation-runs", json={"top_n": 1}, headers=HDR
    ).json()["runs"]
    run_id = created[0]["id"]

    r = admin_client.get(f"/generation-runs/{run_id}", headers=HDR)
    assert r.status_code == 200
    assert r.json()["id"] == run_id


def test_get_by_id_unknown_returns_404(admin_client) -> None:
    r = admin_client.get("/generation-runs/not-a-real-id", headers=HDR)
    assert r.status_code == 404


def test_get_steps_for_new_run_is_empty(admin_client) -> None:
    _seed_clusters(admin_client)
    run_id = admin_client.post(
        "/generation-runs", json={"top_n": 1}, headers=HDR
    ).json()["runs"][0]["id"]

    r = admin_client.get(f"/generation-runs/{run_id}/steps", headers=HDR)
    assert r.status_code == 200
    assert r.json() == []


def test_get_artifacts_for_new_run_is_empty(admin_client) -> None:
    _seed_clusters(admin_client)
    run_id = admin_client.post(
        "/generation-runs", json={"top_n": 1}, headers=HDR
    ).json()["runs"][0]["id"]

    r = admin_client.get(f"/generation-runs/{run_id}/artifacts", headers=HDR)
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# Cancel.
# ---------------------------------------------------------------------------


def test_cancel_queued_run_flips_to_cancelled(admin_client, session) -> None:
    _seed_clusters(admin_client)
    run_id = admin_client.post(
        "/generation-runs", json={"top_n": 1}, headers=HDR
    ).json()["runs"][0]["id"]

    r = admin_client.post(f"/generation-runs/{run_id}/cancel", headers=HDR)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "cancelled"
    assert body["finished_at"] is not None


def test_cancel_already_terminal_returns_409(admin_client, session) -> None:
    _seed_clusters(admin_client)
    run_id = admin_client.post(
        "/generation-runs", json={"top_n": 1}, headers=HDR
    ).json()["runs"][0]["id"]

    admin_client.post(f"/generation-runs/{run_id}/cancel", headers=HDR)
    r2 = admin_client.post(f"/generation-runs/{run_id}/cancel", headers=HDR)
    assert r2.status_code == 409


def test_cancel_unknown_returns_404(admin_client) -> None:
    r = admin_client.post("/generation-runs/not-a-real-id/cancel", headers=HDR)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Safety regression: SystemLog payload for generation events stays whitelisted.
# ---------------------------------------------------------------------------


def test_systemlog_generation_events_only_have_whitelisted_keys(
    admin_client, session
) -> None:
    from chief_editor.models import SystemLog

    _seed_clusters(admin_client)
    run_id = admin_client.post(
        "/generation-runs", json={"top_n": 1}, headers=HDR
    ).json()["runs"][0]["id"]
    admin_client.post(f"/generation-runs/{run_id}/cancel", headers=HDR)

    allowed = {"run_id", "status", "step_count", "duration_ms", "error_class"}
    rows = list(
        session.exec(
            select(SystemLog).where(SystemLog.event.like("generation.%"))  # type: ignore[attr-defined]
        ).all()
    )
    assert rows, "expected at least one generation.* SystemLog row"
    for row in rows:
        for key in (row.data or {}):
            assert key in allowed, (
                f"generation.* SystemLog row {row.event} has non-whitelisted key '{key}'"
            )


def test_no_generation_step_or_artifact_created_in_phase1(admin_client, session) -> None:
    """Phase 1 only enqueues runs. No worker is running in TestClient, so
    no GenerationStep or GenerationArtifact rows should exist after POST."""
    _seed_clusters(admin_client)
    admin_client.post("/generation-runs", json={"top_n": 2}, headers=HDR)
    assert session.exec(select(GenerationStep)).all() == []
    assert session.exec(select(GenerationArtifact)).all() == []
    runs = session.exec(select(GenerationRun)).all()
    assert all(r.status == "queued" for r in runs)
