"""High-level pipeline: collect → dedup → cluster → score."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta

from sqlmodel import Session, select

from ..collectors import CollectedItem, get_collector_for
from ..models import RawItem, Source, StyleProfile, TrendCluster, TrendSignal
from ..time_utils import utcnow
from .dedup import assign_cluster, text_hash, tokens
from .trend_scoring import score_cluster

log = logging.getLogger(__name__)


def _recent_clusters(session: Session, days: int = 7) -> list[TrendCluster]:
    since = utcnow() - timedelta(days=days)
    return list(
        session.exec(
            select(TrendCluster).where(
                (TrendCluster.last_seen_at >= since) | (TrendCluster.created_at >= since)
            )
        ).all()
    )


def ingest_items(session: Session, source: Source, items: list[CollectedItem]) -> int:
    if not items:
        return 0
    inserted = 0
    existing_ids = {
        row.external_id
        for row in session.exec(
            select(RawItem).where(RawItem.source_id == source.id)
        ).all()
    }
    for item in items:
        if item.external_id in existing_ids:
            continue
        combined = f"{item.title}\n{item.body}".strip()
        if not combined:
            continue
        raw = RawItem(
            source_id=source.id,
            external_id=item.external_id,
            title=item.title,
            body=item.body,
            url=item.url,
            lang=item.lang,
            engagement=item.engagement,
            posted_at=item.posted_at,
            collected_at=utcnow(),
            text_hash=text_hash(combined),
        )
        session.add(raw)
        inserted += 1
    source.last_collected_at = utcnow()
    source.health = {
        **(source.health or {}),
        "last_inserted": inserted,
        "last_attempt_at": utcnow().isoformat(),
        "ok": True,
    }
    session.add(source)
    session.commit()
    return inserted


def recluster(session: Session) -> int:
    style = session.exec(select(StyleProfile).where(StyleProfile.name == "default")).first()
    sources = {s.id: s for s in session.exec(select(Source)).all()}

    raw_items = list(
        session.exec(
            select(RawItem).order_by(RawItem.posted_at.desc()).limit(400)
        ).all()
    )
    if not raw_items:
        return 0

    existing_clusters = _recent_clusters(session)
    existing_signals = {
        sig.raw_item_id: sig
        for sig in session.exec(select(TrendSignal)).all()
    }

    cluster_reps: list[tuple[str, str]] = [
        (c.id, c.representative_text) for c in existing_clusters
    ]

    new_signals = 0
    cluster_member_items: dict[str, list[RawItem]] = defaultdict(list)
    by_id = {c.id: c for c in existing_clusters}

    for item in raw_items:
        combined = f"{item.title}\n{item.body}".strip()
        if not combined:
            continue
        if item.id in existing_signals:
            sig = existing_signals[item.id]
            cluster_member_items[sig.cluster_id].append(item)
            continue

        match = assign_cluster(combined, cluster_reps)
        if match is None:
            cluster = TrendCluster(
                representative_text=combined[:240],
                keywords=sorted(tokens(combined))[:8],
                category=item.lang or "ru",
                signal_count=1,
                first_seen_at=item.posted_at or utcnow(),
                last_seen_at=item.posted_at or utcnow(),
                score_breakdown={},
                total_score=0.0,
                sources_summary=[],
            )
            session.add(cluster)
            session.flush()
            cluster_reps.append((cluster.id, cluster.representative_text))
            by_id[cluster.id] = cluster
            session.add(
                TrendSignal(cluster_id=cluster.id, raw_item_id=item.id, similarity=1.0)
            )
            cluster_member_items[cluster.id].append(item)
            new_signals += 1
            continue

        cluster = by_id.get(match.cluster_id)
        if cluster is None:
            cluster = session.get(TrendCluster, match.cluster_id)
            by_id[match.cluster_id] = cluster
        if cluster is None:
            continue
        session.add(
            TrendSignal(
                cluster_id=cluster.id, raw_item_id=item.id, similarity=match.similarity
            )
        )
        cluster_member_items[cluster.id].append(item)
        new_signals += 1

    recent_reps = [c.representative_text for c in existing_clusters]
    for cluster_id, members in cluster_member_items.items():
        cluster = by_id.get(cluster_id) or session.get(TrendCluster, cluster_id)
        if cluster is None:
            continue
        items_with_weights = [
            (it, sources.get(it.source_id).weight if sources.get(it.source_id) else 5.0)
            for it in members
        ]
        breakdown = score_cluster(items_with_weights, recent_reps, style)
        cluster.score_breakdown = breakdown.as_dict()
        cluster.total_score = breakdown.total
        cluster.signal_count = max(
            cluster.signal_count,
            session.exec(
                select(TrendSignal).where(TrendSignal.cluster_id == cluster.id)
            ).all().__len__(),
        )
        cluster.last_seen_at = max(
            (m.posted_at for m in members if m.posted_at), default=cluster.last_seen_at
        )

        def _engagement_total(m: RawItem) -> int:
            if not m.engagement:
                return 0
            return sum(int(v) for v in m.engagement.values() if isinstance(v, (int | float)))

        best = max(members, key=_engagement_total)
        cluster.representative_text = (
            f"{best.title}\n{best.body}".strip() or cluster.representative_text
        )[:240]
        cluster.keywords = sorted(tokens(cluster.representative_text))[:8]
        cluster.sources_summary = _summarize_sources(members, sources)
        cluster.updated_at = utcnow()
        session.add(cluster)

    session.commit()
    return new_signals


def _summarize_sources(
    items: list[RawItem], sources: dict[str, Source]
) -> list[dict]:
    by_source: dict[str, int] = defaultdict(int)
    for it in items:
        s = sources.get(it.source_id)
        if s is None:
            continue
        by_source[s.handle] += 1
    return [
        {"handle": handle, "count": count}
        for handle, count in sorted(by_source.items(), key=lambda x: x[1], reverse=True)
    ]


async def run_collection_for_source(session: Session, source: Source) -> int:
    collector = get_collector_for(source)
    try:
        items = await collector.fetch(source)
    except Exception as exc:  # noqa: BLE001
        log.exception("collector failed for source=%s", source.handle)
        source.health = {
            **(source.health or {}),
            "ok": False,
            "last_error": str(exc)[:200],
            "last_attempt_at": utcnow().isoformat(),
        }
        session.add(source)
        session.commit()
        return 0
    return ingest_items(session, source, items)
