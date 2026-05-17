from chief_editor.models import ApprovalDecision, PostCandidate, PublishJob
from chief_editor.publishing.mock import MockPublisher
from chief_editor.time_utils import utcnow


def test_mock_publisher_returns_outcome() -> None:
    cand = PostCandidate(topic="x", tg_version="hi", threads_version="hello there", status="approved")
    decision = ApprovalDecision(candidate_id=cand.id, decision="approve")
    job = PublishJob(
        candidate_id=cand.id,
        approval_id=decision.id,
        platform="threads",
        scheduled_at=utcnow(),
        idempotency_key="k1",
    )
    outcome = MockPublisher().publish(job, cand, approval=decision)
    assert outcome.success is True
    assert "threads" in outcome.external_url
