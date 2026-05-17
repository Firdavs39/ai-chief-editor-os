from chief_editor.models import (
    ApprovalDecision,
    MetricSnapshot,
    PostCandidate,
    PublishJob,
    PublishResult,
    RawItem,
    Source,
    StyleProfile,
    SystemLog,
    TrendCluster,
    TrendSignal,
)
from chief_editor.time_utils import utcnow


def test_create_each_model(session) -> None:
    src = Source(kind="rss", handle="test", url="https://example.com/rss", weight=5.0)
    session.add(src)
    session.commit()

    raw = RawItem(
        source_id=src.id,
        external_id="x1",
        title="t",
        body="b",
        url="u",
        text_hash="h",
        posted_at=utcnow(),
    )
    cluster = TrendCluster(representative_text="rep", keywords=["a"], category="ru")
    style = StyleProfile(name="default", tone="t", audience="a")
    session.add_all([raw, cluster, style])
    session.commit()

    sig = TrendSignal(cluster_id=cluster.id, raw_item_id=raw.id, similarity=1.0)
    cand = PostCandidate(cluster_id=cluster.id, topic="topic", tg_version="ru text", status="draft")
    session.add_all([sig, cand])
    session.commit()

    appr = ApprovalDecision(candidate_id=cand.id, decision="approve")
    session.add(appr)
    session.commit()

    job = PublishJob(
        candidate_id=cand.id,
        approval_id=appr.id,
        platform="mock",
        scheduled_at=utcnow(),
        idempotency_key="k1",
    )
    session.add(job)
    session.commit()

    res = PublishResult(job_id=job.id, success=True)
    snap = MetricSnapshot(subject_type="candidate", subject_id=cand.id, metrics={"x": 1})
    logr = SystemLog(level="info", event="test")
    session.add_all([res, snap, logr])
    session.commit()

    assert session.get(Source, src.id) is not None
    assert session.get(PostCandidate, cand.id).status == "draft"
