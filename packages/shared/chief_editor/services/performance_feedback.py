"""Phase 12 — performance feedback loop (TG view-counts → trend scoring).

When a candidate is published to Telegram, we can fetch the post's
view-count via Bot API `getChat` / message metadata for the next ~14 days
and record snapshots in `metric_snapshots`. The aggregate of those views
feeds back into `score_breakdown.engagement` so future trend ranking
reflects what actually performed.

Safety properties:
- READ-ONLY against Telegram (`getMessage` / `getChat` — no send/edit).
- Bounded read window (default 14 days) so a viral old post doesn't
  permanently distort scoring.
- Engagement boost is CAPPED at +0.15 absolute on `score_breakdown.engagement`
  to prevent runaway feedback (same topic re-published every day).

This is scaffold. The TG API hook itself is implemented in
`chief_editor.collectors.telegram_views` (separate file, separate PR)
when Phase 12 is staffed.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from ..models import MetricSnapshot, PostCandidate, TrendCluster
from ..time_utils import to_utc, utcnow

log = logging.getLogger(__name__)

# Bounded engagement boost. NEVER raise this without an explicit
# product-owner sign-off in the PR description.
MAX_ENGAGEMENT_BOOST = 0.15
TRACKING_WINDOW_DAYS = 14


def record_view_snapshot(
    session: Session,
    *,
    candidate_id: str,
    platform: str,
    views: int,
    extra: dict[str, Any] | None = None,
) -> MetricSnapshot:
    """Store one observation of how a published post is performing.

    Uses the canonical `MetricSnapshot` schema: subject_type='candidate',
    subject_id=candidate_id, metrics={'platform': ..., 'views': ..., ...}.
    """
    metrics: dict[str, Any] = {"platform": platform, "views": int(views)}
    if extra:
        metrics.update(extra)
    snap = MetricSnapshot(
        subject_type="candidate",
        subject_id=candidate_id,
        metrics=metrics,
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def _within_window(snap: MetricSnapshot) -> bool:
    if not snap.captured_at:
        return False
    cutoff = utcnow() - timedelta(days=TRACKING_WINDOW_DAYS)
    # SQLite returns naive datetimes; normalize before comparing so we
    # don't crash with "can't compare offset-naive and offset-aware".
    return to_utc(snap.captured_at) >= cutoff


def compute_engagement_boost_for_cluster(
    session: Session, cluster_id: str
) -> float:
    """Engagement boost in [0, MAX_ENGAGEMENT_BOOST] computed from the
    median views of recent published candidates in this cluster's lineage.

    The formula is intentionally simple:
        boost = min(MAX_ENGAGEMENT_BOOST,
                    median_recent_views / typical_baseline_views * 0.15)

    where `typical_baseline_views` is currently a hard-coded constant
    (1000) — the Phase 12 follow-up replaces this with a per-channel
    baseline computed from history.

    Returns 0.0 when there are no qualifying snapshots.
    """
    candidates = list(
        session.exec(
            select(PostCandidate).where(PostCandidate.cluster_id == cluster_id)
        ).all()
    )
    if not candidates:
        return 0.0
    cand_ids = [c.id for c in candidates if c.status == "published"]
    if not cand_ids:
        return 0.0

    snaps = list(
        session.exec(
            select(MetricSnapshot)
            .where(MetricSnapshot.subject_type == "candidate")
            .where(MetricSnapshot.subject_id.in_(cand_ids))  # type: ignore[attr-defined]
        ).all()
    )
    snaps = [s for s in snaps if _within_window(s)]
    if not snaps:
        return 0.0

    views = sorted([
        int(s.metrics.get("views", 0)) for s in snaps if (s.metrics or {}).get("views") is not None
    ])
    if not views:
        return 0.0
    median_views = views[len(views) // 2]

    # Hard-coded baseline; replace with per-channel learned baseline later.
    baseline = 1000
    raw = (median_views / max(baseline, 1)) * MAX_ENGAGEMENT_BOOST
    return min(MAX_ENGAGEMENT_BOOST, max(0.0, raw))


def apply_engagement_boost(session: Session, cluster: TrendCluster) -> float:
    """Update cluster.score_breakdown['engagement'] with the new boost,
    cap-aware. Returns the boost that was applied.

    This is opt-in: it must be called explicitly by a scheduler — it does
    NOT run automatically on every cluster scoring pass yet. That's the
    follow-up wire-up after Phase 12 ships its data collector.
    """
    boost = compute_engagement_boost_for_cluster(session, cluster.id)
    if boost <= 0.0:
        return 0.0
    breakdown = dict(cluster.score_breakdown or {})
    # Cap on the FINAL value, not just the increment, so runaway boosts
    # are impossible even if this function is called repeatedly.
    current = float(breakdown.get("engagement", 0.0))
    new_eng = min(1.0, max(0.0, current) + boost)
    breakdown["engagement"] = new_eng
    cluster.score_breakdown = breakdown
    cluster.updated_at = utcnow()
    session.add(cluster)
    session.commit()
    session.refresh(cluster)
    log.info(
        "performance.engagement_boost cluster_id=%s boost=%s new_engagement=%s",
        cluster.id, boost, new_eng,
    )
    return boost


__all__ = [
    "MAX_ENGAGEMENT_BOOST",
    "TRACKING_WINDOW_DAYS",
    "apply_engagement_boost",
    "compute_engagement_boost_for_cluster",
    "record_view_snapshot",
]
