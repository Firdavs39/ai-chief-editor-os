"""Phase 11 + 12 scaffold tests.

Both phases need operator action AND time-in-production data before they
mean anything. These tests pin down the SAFETY properties of the
scaffolds:

- Phase 11 (style learning) MUST NOT mutate StyleProfile silently —
  every change must be a proposal awaiting operator review.
- Phase 12 (performance feedback) caps the engagement boost at 0.15 and
  refuses to look at posts outside a 14-day window — so a single viral
  post can't poison scoring forever.

Once the operator-facing UIs land, these tests grow; for now they lock
the contracts.
"""
from __future__ import annotations

from datetime import timedelta

from chief_editor.models import (
    MetricSnapshot,
    PostCandidate,
    StyleProfile,
    TrendCluster,
)
from chief_editor.services.performance_feedback import (
    MAX_ENGAGEMENT_BOOST,
    TRACKING_WINDOW_DAYS,
    apply_engagement_boost,
    compute_engagement_boost_for_cluster,
    record_view_snapshot,
)
from chief_editor.services.style_learning import (
    MAX_SOURCE_POSTS,
    propose_style_update,
)
from chief_editor.time_utils import utcnow

# ---------------------------------------------------------------------------
# Phase 11 — style learning safety
# ---------------------------------------------------------------------------


def test_style_proposal_is_none_when_no_published_posts(session) -> None:
    """No published history → no proposal. NEVER auto-write rules from
    drafts or unrated posts."""
    session.add(StyleProfile(name="default", tone="экспертный", audience="dev"))
    session.commit()
    proposal = propose_style_update(session)
    assert proposal is None


def test_style_proposal_is_none_without_profile(session) -> None:
    """No default profile → no proposal. Don't fabricate one."""
    proposal = propose_style_update(session)
    assert proposal is None


def test_style_proposal_does_not_mutate_profile(session) -> None:
    """The proposal builder is READ-ONLY against StyleProfile. Calling
    it must not change tone / banned_phrases / writing_rules."""
    profile = StyleProfile(
        name="default", tone="экспертный", audience="dev",
        writing_rules="be specific", banned_phrases=["filler"],
    )
    session.add(profile)

    cluster = TrendCluster(
        representative_text="t", category="ru", keywords=[],
        score_breakdown={}, total_score=0.5,
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)

    cand = PostCandidate(
        cluster_id=cluster.id, topic="x", source_summary="s",
        why_it_matters="w", psychology_hook="h",
        tg_version="a", threads_version="b", reddit_version="c",
        cta="cta", status="published",
    )
    session.add(cand)
    session.commit()

    before_tone = profile.tone
    before_banned = list(profile.banned_phrases or [])
    before_rules = profile.writing_rules

    proposal = propose_style_update(session)
    assert proposal is not None

    session.refresh(profile)
    assert profile.tone == before_tone
    assert list(profile.banned_phrases or []) == before_banned
    assert profile.writing_rules == before_rules


def test_style_proposal_cap_documented_in_module() -> None:
    """Documented invariant: never learn from more than 30 posts at once."""
    assert MAX_SOURCE_POSTS == 30


# ---------------------------------------------------------------------------
# Phase 12 — performance feedback safety
# ---------------------------------------------------------------------------


def test_engagement_boost_capped_at_constant() -> None:
    """Documented invariant: engagement boost is capped at 0.15."""
    assert MAX_ENGAGEMENT_BOOST == 0.15


def test_tracking_window_is_two_weeks() -> None:
    """Documented invariant: a post older than 14 days does NOT contribute."""
    assert TRACKING_WINDOW_DAYS == 14


def test_no_snapshots_yields_zero_boost(session) -> None:
    cluster = TrendCluster(
        representative_text="t", category="ru", keywords=[],
        score_breakdown={}, total_score=0.5,
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)
    assert compute_engagement_boost_for_cluster(session, cluster.id) == 0.0


def test_record_view_snapshot_persists_with_canonical_schema(session) -> None:
    """record_view_snapshot uses subject_type/subject_id/metrics — the
    canonical MetricSnapshot schema. Validates we're not silently writing
    to a non-existent column."""
    snap = record_view_snapshot(
        session, candidate_id="cand-123", platform="telegram", views=500
    )
    assert snap.subject_type == "candidate"
    assert snap.subject_id == "cand-123"
    assert snap.metrics["platform"] == "telegram"
    assert snap.metrics["views"] == 500


def test_apply_engagement_boost_caps_at_max(session) -> None:
    """Even when median views are absurd, boost stays at MAX_ENGAGEMENT_BOOST.
    No runaway feedback."""
    cluster = TrendCluster(
        representative_text="t", category="ru", keywords=[],
        score_breakdown={"engagement": 0.5}, total_score=0.5,
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)

    cand = PostCandidate(
        cluster_id=cluster.id, topic="x", source_summary="s",
        why_it_matters="w", psychology_hook="h",
        tg_version="a", threads_version="b", reddit_version="c",
        cta="cta", status="published",
    )
    session.add(cand)
    session.commit()
    session.refresh(cand)

    # 10 snapshots of 1,000,000 views each — well above any baseline
    for _ in range(10):
        record_view_snapshot(
            session, candidate_id=cand.id, platform="telegram", views=1_000_000
        )

    boost = apply_engagement_boost(session, cluster)
    assert 0.0 < boost <= MAX_ENGAGEMENT_BOOST  # capped


def test_old_snapshots_are_ignored(session) -> None:
    """Snapshots captured outside the tracking window must NOT count."""
    cluster = TrendCluster(
        representative_text="t", category="ru", keywords=[],
        score_breakdown={}, total_score=0.5,
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)

    cand = PostCandidate(
        cluster_id=cluster.id, topic="x", source_summary="s",
        why_it_matters="w", psychology_hook="h",
        tg_version="a", threads_version="b", reddit_version="c",
        cta="cta", status="published",
    )
    session.add(cand)
    session.commit()
    session.refresh(cand)

    # Create a snapshot but backdate it past the window
    old = MetricSnapshot(
        subject_type="candidate", subject_id=cand.id,
        metrics={"platform": "telegram", "views": 5_000_000},
        captured_at=utcnow() - timedelta(days=TRACKING_WINDOW_DAYS + 1),
    )
    session.add(old)
    session.commit()

    assert compute_engagement_boost_for_cluster(session, cluster.id) == 0.0
