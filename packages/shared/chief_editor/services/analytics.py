"""Analytics aggregation. Reads from MetricSnapshot + related tables."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlmodel import Session, select

from ..models import MetricSnapshot, PostCandidate, PublishJob, Source
from ..time_utils import utcnow


def _hook_bucket(hook: str) -> str:
    h = hook.lower()
    if any(w in h for w in ("никто", "тихая", "самое", "неудобн")):
        return "contrarian"
    if "если" in h or "как " in h:
        return "instructional"
    if "?" in h:
        return "question"
    return "observation"


def build_analytics(session: Session) -> dict[str, Any]:
    candidates = session.exec(select(PostCandidate)).all()
    jobs = session.exec(select(PublishJob)).all()
    sources = {s.id: s for s in session.exec(select(Source)).all()}
    snapshots = session.exec(
        select(MetricSnapshot).where(MetricSnapshot.captured_at >= utcnow() - timedelta(days=14))
    ).all()

    by_candidate_id = {c.id: c for c in candidates}

    by_hook: dict[str, dict[str, float]] = defaultdict(lambda: {"posts": 0, "viral_avg": 0.0, "reach_avg": 0.0})
    for c in candidates:
        bucket = _hook_bucket(c.psychology_hook)
        by_hook[bucket]["posts"] += 1
        by_hook[bucket]["viral_avg"] += c.viral_score
        by_hook[bucket]["reach_avg"] += c.style_match_score

    by_hook_list: list[dict[str, Any]] = []
    for bucket, agg in by_hook.items():
        n = agg["posts"] or 1
        by_hook_list.append(
            {
                "hook_type": bucket,
                "posts": int(agg["posts"]),
                "viral_avg": round(agg["viral_avg"] / n, 2),
                "reach_avg": round(agg["reach_avg"] / n, 2),
            }
        )
    by_hook_list.sort(key=lambda r: r["viral_avg"], reverse=True)

    by_source_map: dict[str, dict[str, float]] = defaultdict(
        lambda: {"posts": 0, "engagement": 0.0, "score_avg": 0.0}
    )
    for snap in snapshots:
        if snap.subject_type != "candidate":
            continue
        cand = by_candidate_id.get(snap.subject_id)
        if cand is None:
            continue
        engagement = float(snap.metrics.get("engagement", 0))
        source_key = snap.metrics.get("source_handle", "—")
        by_source_map[source_key]["posts"] += 1
        by_source_map[source_key]["engagement"] += engagement
        by_source_map[source_key]["score_avg"] += cand.style_match_score

    by_source: list[dict[str, Any]] = []
    for handle, agg in by_source_map.items():
        n = agg["posts"] or 1
        by_source.append(
            {
                "source": handle,
                "posts": int(agg["posts"]),
                "avg_engagement": round(agg["engagement"] / n, 1),
                "avg_style_match": round(agg["score_avg"] / n, 2),
            }
        )
    by_source.sort(key=lambda r: r["avg_engagement"], reverse=True)

    best_patterns: list[dict[str, Any]] = []
    if by_hook_list:
        best_patterns.append(
            {
                "title": "Лучше всего работают «контрарные» крючки",
                "detail": f"средний viral score: {by_hook_list[0]['viral_avg']}",
                "kind": "hook",
            }
        )
    if by_source:
        best_patterns.append(
            {
                "title": f"Источник {by_source[0]['source']} даёт лучший отклик",
                "detail": f"avg engagement: {by_source[0]['avg_engagement']}",
                "kind": "source",
            }
        )
    approved = sum(1 for c in candidates if c.status in {"approved", "published"})
    rejected = sum(1 for c in candidates if c.status == "rejected")
    if approved or rejected:
        ratio = approved / max(1, approved + rejected)
        best_patterns.append(
            {
                "title": "Approval rate",
                "detail": f"{int(ratio * 100)}% утверждено",
                "kind": "ratio",
            }
        )

    learning_timeline: list[dict[str, Any]] = []
    by_day: dict[str, dict[str, float]] = defaultdict(lambda: {"posts": 0, "engagement": 0.0})
    for snap in snapshots:
        day_key = snap.captured_at.date().isoformat()
        by_day[day_key]["posts"] += 1
        by_day[day_key]["engagement"] += float(snap.metrics.get("engagement", 0))
    for day, agg in sorted(by_day.items()):
        n = agg["posts"] or 1
        learning_timeline.append(
            {
                "date": day,
                "posts": int(agg["posts"]),
                "avg_engagement": round(agg["engagement"] / n, 1),
            }
        )

    totals = {
        "candidates": len(candidates),
        "approved": approved,
        "rejected": rejected,
        "scheduled": sum(1 for j in jobs if j.status == "pending"),
        "published": sum(1 for j in jobs if j.status == "done"),
        "sources": len(sources),
    }

    return {
        "by_hook_type": by_hook_list,
        "by_source": by_source,
        "best_patterns": best_patterns,
        "learning_timeline": learning_timeline,
        "totals": totals,
    }
