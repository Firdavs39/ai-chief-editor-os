"""HTTP-level safety regressions.

These hit the API through TestClient (the path the Vercel frontend uses) and
verify that the three flags — `PUBLISHING_ENABLED`, `DRY_RUN_PUBLISH`,
approval — observably enforce the gate at every customer-visible surface.

Pure unit tests of `_dispatch_one()` already exist in test_publishing_safety.py.
These add the layer above: the dry-run preview endpoint, plus the full
approve → worker tick → assert candidate not published chain via TestClient.
"""

from __future__ import annotations

from sqlmodel import select

from chief_editor.models import PublishJob, PublishResult
from chief_editor.settings import get_settings


def _seed_and_pick_draft_id(client) -> str:
    client.post("/demo/seed")
    drafts = client.get("/candidates?status=draft").json()
    return drafts[0]["id"]


# ---------------------------------------------------------------------------
# /readiness/dry-run-publish — would_send must be false in default mode
# ---------------------------------------------------------------------------


def test_dry_run_preview_endpoint_returns_would_send_false(client) -> None:
    cand_id = _seed_and_pick_draft_id(client)
    res = client.post(f"/readiness/dry-run-publish/{cand_id}?platform=telegram")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "preview" in body
    preview = body["preview"]
    assert preview["dry_run"] is True
    assert preview["would_send"] is False, (
        "would_send must be false unless publishing_enabled=true AND "
        "dry_run_publish=false AND mock_mode=false — defaults must not satisfy that"
    )
    # Payload must include the computed body and platform-aware limits.
    assert preview["platform"] == "telegram"
    assert preview["body_length"] == len(preview["body"])
    assert preview["limits"]["max_length"] == 4096


def test_dry_run_preview_safety_block_reflects_current_flags(client) -> None:
    """The `safety` sub-dict in the preview must mirror current settings."""
    cand_id = _seed_and_pick_draft_id(client)
    res = client.post(f"/readiness/dry-run-publish/{cand_id}?platform=threads")
    safety = res.json()["preview"]["safety"]
    s = get_settings()
    assert safety["publishing_enabled"] == s.publishing_enabled
    assert safety["dry_run_publish"] == s.dry_run_publish
    assert safety["mock_mode"] == s.mock_mode


def test_dry_run_preview_unknown_candidate_404(client) -> None:
    res = client.post("/readiness/dry-run-publish/does-not-exist?platform=telegram")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Approve → worker dispatch with PUBLISHING_ENABLED=false → blocked
# ---------------------------------------------------------------------------


def test_approve_then_worker_dispatch_blocks_with_publishing_off(
    client, session, monkeypatch
) -> None:
    """End-to-end safety: approve via HTTP, then call _dispatch_one directly
    with PUBLISHING_ENABLED=false. Job must transition to `blocked` and
    candidate must NOT be marked published.
    """
    monkeypatch.setenv("PUBLISHING_ENABLED", "false")
    monkeypatch.setenv("DRY_RUN_PUBLISH", "false")
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()

    cand_id = _seed_and_pick_draft_id(client)
    approve = client.post(
        f"/approvals/{cand_id}/approve",
        json={"platform": "telegram"},
    )
    assert approve.status_code == 200
    job_id = approve.json()["job"]["id"]

    # Pull the job into the in-memory session and dispatch it through the
    # same code the worker would run.
    from worker.main import _dispatch_one

    job = session.get(PublishJob, job_id)
    assert job is not None and job.status == "pending"

    _dispatch_one(session, job)
    session.commit()
    session.refresh(job)

    assert job.status == "blocked", (
        f"PUBLISHING_ENABLED=false should yield blocked, got {job.status}"
    )

    result = session.exec(
        select(PublishResult).where(PublishResult.job_id == job.id)
    ).first()
    assert result is not None
    assert result.success is False
    assert "PUBLISHING_ENABLED" in result.error

    # Most important assertion of this whole module.
    cand_after = client.get(f"/candidates/{cand_id}").json()
    assert cand_after["status"] == "approved", (
        f"candidate must stay approved (never published) when publishing is "
        f"disabled, got {cand_after['status']}"
    )


def test_approve_then_worker_dispatch_dry_run_does_not_publish(
    client, session, monkeypatch
) -> None:
    """Same flow but with PUBLISHING_ENABLED=true + DRY_RUN_PUBLISH=true.
    Job must transition to `dry_run`, candidate must remain `approved`.
    """
    monkeypatch.setenv("PUBLISHING_ENABLED", "true")
    monkeypatch.setenv("DRY_RUN_PUBLISH", "true")
    monkeypatch.setenv("MOCK_MODE", "true")
    get_settings.cache_clear()

    cand_id = _seed_and_pick_draft_id(client)
    approve = client.post(
        f"/approvals/{cand_id}/approve",
        json={"platform": "telegram"},
    )
    job_id = approve.json()["job"]["id"]

    from worker.main import _dispatch_one

    job = session.get(PublishJob, job_id)
    _dispatch_one(session, job)
    session.commit()
    session.refresh(job)

    assert job.status == "dry_run"

    result = session.exec(
        select(PublishResult).where(PublishResult.job_id == job.id)
    ).first()
    assert result is not None
    assert result.success is True
    assert result.external_url.startswith("dryrun://")

    cand_after = client.get(f"/candidates/{cand_id}").json()
    assert cand_after["status"] == "approved", (
        "dry-run dispatch must NOT mark candidate as published"
    )
