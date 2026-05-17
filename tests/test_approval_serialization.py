"""Regression tests for the approve/reject HTTP serialization bug.

Before the fix, `approve_and_schedule()` / `reject_candidate()` ended with
`session.commit()` which expires all instance attributes in SQLAlchemy.
Pydantic v2's `model_dump()` reads `__dict__` directly without triggering
lazy-load, so `CandidateOut(**candidate.model_dump())` would explode with
`Field required` errors and the route returned HTTP 500 — even though the
underlying approval/reject was committed.

Fix: explicit `session.refresh(candidate)` after commit in both services.

These tests guard against regression at the HTTP boundary, which is the
layer that actually hit the bug. Pure unit tests on the service functions
miss it because attribute access via dot syntax lazy-loads transparently.
"""

from __future__ import annotations


def _seed_and_pick_draft(client) -> str:
    """Seed the DB once, return the id of a draft candidate."""
    seed = client.post("/demo/seed")
    assert seed.status_code == 200
    drafts = client.get("/candidates?status=draft").json()
    assert drafts, "demo seed should produce at least one draft candidate"
    return drafts[0]["id"]


# ---------------------------------------------------------------------------
# Approve — full candidate payload returned
# ---------------------------------------------------------------------------


def test_approve_endpoint_returns_200_not_500(client) -> None:
    cand_id = _seed_and_pick_draft(client)
    res = client.post(
        f"/approvals/{cand_id}/approve",
        json={"platform": "telegram", "reason": "regression"},
    )
    assert res.status_code == 200, (
        f"approve returned {res.status_code} — body: {res.text[:300]}"
    )


def test_approve_response_includes_full_candidate_payload(client) -> None:
    cand_id = _seed_and_pick_draft(client)
    res = client.post(
        f"/approvals/{cand_id}/approve",
        json={"platform": "telegram", "reason": "regression"},
    )
    body = res.json()
    assert "candidate" in body, f"missing candidate key: {body}"
    cand = body["candidate"]

    # If the model_dump bug regresses, the dict is empty and these all KeyError.
    for required in (
        "id",
        "status",
        "topic",
        "tg_version",
        "threads_version",
        "reddit_version",
        "cta",
        "style_match_score",
        "viral_score",
        "slop_risk",
        "controversy_risk",
        "recommendation",
        "critic_notes",
        "version",
        "created_at",
    ):
        assert required in cand, f"approve response missing field: {required}"

    assert cand["id"] == cand_id
    assert cand["status"] == "approved"
    assert isinstance(cand["topic"], str) and cand["topic"]
    assert isinstance(cand["version"], int)


def test_approve_response_includes_full_job_payload(client) -> None:
    cand_id = _seed_and_pick_draft(client)
    res = client.post(
        f"/approvals/{cand_id}/approve",
        json={"platform": "telegram", "reason": "regression"},
    )
    body = res.json()
    assert "job" in body, f"missing job key: {body}"
    job = body["job"]
    for required in (
        "id",
        "candidate_id",
        "approval_id",
        "platform",
        "scheduled_at",
        "status",
        "idempotency_key",
        "created_at",
    ):
        assert required in job, f"job payload missing field: {required}"
    assert job["candidate_id"] == cand_id
    assert job["platform"] == "telegram"
    # Worker is the gate that flips this to blocked/dry_run/done — not the route.
    assert job["status"] == "pending"


def test_approve_response_includes_approval_id(client) -> None:
    cand_id = _seed_and_pick_draft(client)
    res = client.post(
        f"/approvals/{cand_id}/approve",
        json={"platform": "telegram"},
    )
    body = res.json()
    assert "approval_id" in body and body["approval_id"], body


def test_approve_then_get_candidate_consistent(client) -> None:
    """The candidate fetched after approve must agree with the approve response."""
    cand_id = _seed_and_pick_draft(client)
    approve = client.post(
        f"/approvals/{cand_id}/approve",
        json={"platform": "telegram"},
    ).json()["candidate"]
    fetched = client.get(f"/candidates/{cand_id}").json()
    assert fetched["status"] == approve["status"] == "approved"
    assert fetched["topic"] == approve["topic"]
    assert fetched["tg_version"] == approve["tg_version"]


# ---------------------------------------------------------------------------
# Reject — full candidate payload returned
# ---------------------------------------------------------------------------


def test_reject_endpoint_returns_200_not_500(client) -> None:
    cand_id = _seed_and_pick_draft(client)
    res = client.post(
        f"/approvals/{cand_id}/reject",
        json={"platform": "telegram", "reason": "regression"},
    )
    assert res.status_code == 200, (
        f"reject returned {res.status_code} — body: {res.text[:300]}"
    )


def test_reject_response_includes_full_candidate_payload(client) -> None:
    cand_id = _seed_and_pick_draft(client)
    res = client.post(
        f"/approvals/{cand_id}/reject",
        json={"platform": "telegram", "reason": "regression"},
    )
    cand = res.json()
    for required in ("id", "status", "topic", "tg_version", "version", "created_at"):
        assert required in cand, f"reject response missing field: {required}"
    assert cand["id"] == cand_id
    assert cand["status"] == "rejected"
    assert isinstance(cand["topic"], str) and cand["topic"]


def test_reject_then_get_candidate_consistent(client) -> None:
    cand_id = _seed_and_pick_draft(client)
    reject = client.post(
        f"/approvals/{cand_id}/reject",
        json={"platform": "telegram"},
    ).json()
    fetched = client.get(f"/candidates/{cand_id}").json()
    assert fetched["status"] == reject["status"] == "rejected"
    assert fetched["topic"] == reject["topic"]


# ---------------------------------------------------------------------------
# model_dump-style serialization is safe on the underlying service path too
# ---------------------------------------------------------------------------


def test_approve_service_returns_refreshed_candidate(session) -> None:
    """Service-level guard: calling model_dump() on candidate after the service
    returns must produce a populated dict (not the post-commit-expired {})."""
    from chief_editor.models import PostCandidate
    from chief_editor.services.approval import approve_and_schedule

    cand = PostCandidate(
        topic="regression-fixture",
        tg_version="hi",
        threads_version="hi",
        reddit_version="hi",
        cta="Do it.",
        status="draft",
    )
    session.add(cand)
    session.commit()

    _, _ = approve_and_schedule(session, cand, platform="telegram")
    dumped = cand.model_dump()
    assert dumped, "candidate.model_dump() returned empty dict after approve_and_schedule"
    assert dumped.get("status") == "approved"
    assert dumped.get("topic") == "regression-fixture"
    assert dumped.get("tg_version") == "hi"


def test_reject_service_returns_refreshed_candidate(session) -> None:
    from chief_editor.models import PostCandidate
    from chief_editor.services.approval import reject_candidate

    cand = PostCandidate(
        topic="regression-reject",
        tg_version="hi",
        threads_version="hi",
        reddit_version="hi",
        cta="Skip.",
        status="draft",
    )
    session.add(cand)
    session.commit()

    reject_candidate(session, cand, reason="bad")
    dumped = cand.model_dump()
    assert dumped, "candidate.model_dump() returned empty dict after reject_candidate"
    assert dumped.get("status") == "rejected"
    assert dumped.get("topic") == "regression-reject"
