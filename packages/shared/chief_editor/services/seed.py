"""Demo data seed. Wipes tables and inserts realistic Russian-first content."""

from __future__ import annotations

import asyncio
import random
from datetime import timedelta

from sqlmodel import Session, delete, select

from ..db import init_db, session_scope
from ..models import (
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
from ..time_utils import utcnow
from .approval import approve_and_schedule
from .candidate import generate_for_cluster
from .pipeline import recluster, run_collection_for_source

_DEMO_SOURCES = [
    {
        "kind": "telegram",
        "handle": "@durov",
        "url": "https://t.me/durov",
        "title": "Pavel Durov",
        "weight": 9.0,
    },
    {
        "kind": "telegram",
        "handle": "@TechProRu",
        "url": "https://t.me/TechProRu",
        "title": "TechPro RU",
        "weight": 7.5,
    },
    {
        "kind": "reddit",
        "handle": "r/creatoreconomy",
        "url": "https://reddit.com/r/creatoreconomy",
        "title": "Creator Economy",
        "weight": 7.0,
    },
    {
        "kind": "reddit",
        "handle": "r/socialmedia",
        "url": "https://reddit.com/r/socialmedia",
        "title": "Social Media",
        "weight": 6.5,
    },
    {
        "kind": "rss",
        "handle": "anthropic-news",
        "url": "https://www.anthropic.com/news/rss.xml",
        "title": "Anthropic News",
        "weight": 8.5,
    },
    {
        "kind": "rss",
        "handle": "vc-ru-tech",
        "url": "https://vc.ru/rss/tech",
        "title": "VC.ru — Tech",
        "weight": 6.0,
    },
]

_DEMO_STYLE = {
    "tone": "Экспертно, по-человечески, без воды. Прямой разговор с думающим читателем.",
    "audience": "Создатели контента и продактовые маркетологи 24-40 лет, ru-RU.",
    "lang_primary": "ru",
    "banned_phrases": [
        "в эпоху технологий",
        "давайте погрузимся",
        "не секрет, что",
        "в современном мире",
        "стоит отметить",
    ],
    "example_posts": [
        "Я перестал верить в большие охваты. Маленькая, но горячая аудитория монетизируется в 8 раз лучше — и не выгорает.",
        "Threads — это новый ru-Twitter, только без токсичности и с алгоритмом, который любит длинные мысли. Кто заметил это раньше всех, уже собирает аудиторию бесплатно.",
        "AI-редактор — не тот, кто пишет за тебя. Это тот, кто говорит «здесь скучно» — и заставляет переписать сцену.",
    ],
    "writing_rules": (
        "1) Первые 80 символов — крючок, не вступление. "
        "2) Один пост — одна мысль. "
        "3) Цифры или конкретный пример обязательны. "
        "4) Никаких канцеляризмов и ИИ-штампов. "
        "5) CTA — повелительный глагол, не вопрос."
    ),
    "target_topics": [
        "AI и контент", "creator economy", "Telegram-рост", "Threads",
        "монетизация контента", "редактура", "stylometry",
    ],
    "voice_sliders": {
        "expert": 0.85, "playful": 0.4, "contrarian": 0.7, "warm": 0.6,
    },
}

_HOOKS_LIBRARY = [
    "Никто не говорит об этом вслух, но",
    "Самое неудобное наблюдение недели:",
    "Тихая революция, которую все пропустили:",
    "Если коротко, индустрия снова сделала разворот —",
]


def _wipe(session: Session) -> None:
    for model in (
        PublishResult, PublishJob, ApprovalDecision, PostCandidate,
        TrendSignal, TrendCluster, RawItem, MetricSnapshot,
        SystemLog, Source, StyleProfile,
    ):
        session.exec(delete(model))
    session.commit()


def _ensure_style(session: Session) -> StyleProfile:
    profile = StyleProfile(name="default", **_DEMO_STYLE)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def _seed_sources(session: Session) -> list[Source]:
    sources: list[Source] = []
    for entry in _DEMO_SOURCES:
        s = Source(
            kind=entry["kind"],
            handle=entry["handle"],
            url=entry["url"],
            title=entry["title"],
            weight=entry["weight"],
            enabled=True,
            health={"ok": True, "note": "seeded"},
        )
        session.add(s)
        sources.append(s)
    session.commit()
    for s in sources:
        session.refresh(s)
    return sources


async def _seed_raw_for(session: Session, sources: list[Source]) -> None:
    for src in sources:
        await run_collection_for_source(session, src)


def _seed_publish_history(session: Session, candidates: list[PostCandidate]) -> None:
    if len(candidates) < 3:
        return
    now = utcnow()
    # Published one (done)
    cand = candidates[0]
    decision, job = approve_and_schedule(
        session, cand, platform="telegram",
        reason="strong viral score",
        scheduled_at=now - timedelta(hours=4),
    )
    job.status = "done"
    cand.status = "published"
    session.add(job)
    session.add(cand)
    result = PublishResult(
        job_id=job.id,
        external_url="https://t.me/demo_channel/421",
        success=True,
        error="",
        metrics_snapshot_at_publish={"views": 14210, "reactions": 612, "shares": 71},
    )
    session.add(result)

    # Future scheduled
    cand2 = candidates[1]
    approve_and_schedule(
        session, cand2, platform="threads",
        reason="experimental hook test",
        scheduled_at=now + timedelta(hours=18),
    )

    # Failed past job
    cand3 = candidates[2]
    _, failed_job = approve_and_schedule(
        session, cand3, platform="telegram",
        reason="quick publish",
        scheduled_at=now - timedelta(hours=2),
    )
    failed_job.status = "failed"
    session.add(failed_job)
    session.add(
        PublishResult(
            job_id=failed_job.id,
            external_url="",
            success=False,
            error="Network timeout (demo)",
            metrics_snapshot_at_publish={},
        )
    )

    # Mark a few candidates rejected for board variety
    for cand_x in candidates[3:5]:
        decision = ApprovalDecision(
            candidate_id=cand_x.id,
            decision="reject",
            actor="local-user",
            reason="слабый крючок (demo)",
        )
        cand_x.status = "rejected"
        session.add(decision)
        session.add(cand_x)

    session.commit()


def _seed_metrics(session: Session, candidates: list[PostCandidate], sources: list[Source]) -> None:
    rng = random.Random(42)
    now = utcnow()
    for c in candidates:
        for day in range(14):
            src = rng.choice(sources)
            snap = MetricSnapshot(
                subject_type="candidate",
                subject_id=c.id,
                metrics={
                    "engagement": int(800 + rng.random() * 4000 * c.viral_score),
                    "reach": int(2000 + rng.random() * 12000 * c.style_match_score),
                    "saves": int(20 + rng.random() * 300),
                    "shares": int(8 + rng.random() * 120),
                    "source_handle": src.handle,
                    "platform": rng.choice(["telegram", "threads", "reddit"]),
                },
                captured_at=now - timedelta(days=day, hours=rng.randint(0, 23)),
            )
            session.add(snap)
    session.commit()


def _seed_logs(session: Session) -> None:
    now = utcnow()
    entries = [
        ("info", "system.boot", "Demo data seeded", {}),
        ("info", "collector.tick", "Mock collector ingested 24 items", {"new": 24}),
        ("warn", "llm.fallback", "anthropic key missing — fell back to mock", {"provider": "mock"}),
        ("info", "scorer.recluster", "Reclustered 12 clusters", {"clusters": 12}),
        ("info", "publisher.dispatch", "Mock publisher delivered post", {"job": "demo"}),
    ]
    for i, (level, event, msg, data) in enumerate(entries):
        session.add(
            SystemLog(
                level=level, event=event, message=msg, data=data,
                created_at=now - timedelta(minutes=i * 7),
                updated_at=now - timedelta(minutes=i * 7),
            )
        )
    session.commit()


def run_seed() -> dict:
    """Reset database tables, then populate realistic demo content."""
    init_db()

    async def _build() -> dict:
        with session_scope() as session:
            _wipe(session)
            _ensure_style(session)
            sources = _seed_sources(session)
            await _seed_raw_for(session, sources)
            recluster(session)

            clusters = list(
                session.exec(
                    select(TrendCluster).order_by(TrendCluster.total_score.desc())
                ).all()
            )
            candidates: list[PostCandidate] = []
            for cluster in clusters[:8]:
                candidates.append(generate_for_cluster(session, cluster))
            _seed_publish_history(session, candidates)
            _seed_metrics(session, candidates, sources)
            _seed_logs(session)

            return {
                "sources": len(sources),
                "raw_items": len(session.exec(select(RawItem)).all()),
                "clusters": len(clusters),
                "candidates": len(candidates),
            }

    return asyncio.run(_build())


if __name__ == "__main__":
    summary = run_seed()
    print("Seed complete:", summary)
