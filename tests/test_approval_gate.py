import pytest

from chief_editor.models import ApprovalDecision, PostCandidate, PublishJob
from chief_editor.publishing import ApprovalRequiredError
from chief_editor.publishing.mock import MockPublisher
from chief_editor.services.approval import approve_and_schedule, reject_candidate
from chief_editor.time_utils import utcnow


def test_publisher_refuses_without_approval() -> None:
    cand = PostCandidate(topic="x", tg_version="hello", status="draft")
    job = PublishJob(
        candidate_id=cand.id,
        approval_id="",
        platform="mock",
        scheduled_at=utcnow(),
        idempotency_key="k",
    )
    publisher = MockPublisher()
    with pytest.raises(ApprovalRequiredError):
        publisher.publish(job, cand, approval=None)


def test_publisher_refuses_reject_decision() -> None:
    cand = PostCandidate(topic="x", tg_version="hello", status="draft")
    decision = ApprovalDecision(candidate_id=cand.id, decision="reject")
    job = PublishJob(
        candidate_id=cand.id,
        approval_id=decision.id,
        platform="mock",
        scheduled_at=utcnow(),
        idempotency_key="k",
    )
    with pytest.raises(ApprovalRequiredError):
        MockPublisher().publish(job, cand, approval=decision)


def test_approve_and_schedule_creates_job(session) -> None:
    cand = PostCandidate(topic="x", tg_version="hi", status="draft")
    session.add(cand)
    session.commit()
    decision, job = approve_and_schedule(session, cand, platform="telegram")
    assert decision.decision == "approve"
    assert job.candidate_id == cand.id
    assert cand.status == "approved"


def test_publisher_runs_with_approval(session) -> None:
    cand = PostCandidate(topic="x", tg_version="hello world", status="draft")
    session.add(cand)
    session.commit()
    decision, job = approve_and_schedule(session, cand, platform="mock")
    outcome = MockPublisher().publish(job, cand, approval=decision)
    assert outcome.success is True
    assert outcome.external_url.startswith("mock://")


def test_rejected_candidate_blocks_publish(session) -> None:
    cand = PostCandidate(topic="x", tg_version="hi", status="draft")
    session.add(cand)
    session.commit()
    decision = reject_candidate(session, cand, reason="ai-slop")
    assert decision.decision == "reject"
    assert cand.status == "rejected"
    job = PublishJob(
        candidate_id=cand.id,
        approval_id=decision.id,
        platform="mock",
        scheduled_at=utcnow(),
        idempotency_key="k",
    )
    with pytest.raises(ApprovalRequiredError):
        MockPublisher().publish(job, cand, approval=decision)
