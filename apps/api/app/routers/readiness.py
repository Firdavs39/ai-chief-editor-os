"""Readiness + safe test endpoints.

Every endpoint returns HTTP 200 even on configuration problems — callers
discriminate by the `status` field of `ReadinessItem`. We use 4xx only for
classic errors (candidate not found, etc).

No endpoint here may publish content, send a Telegram message, or create
a Postiz post. Test calls are identity / read-only / parse-only.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from chief_editor.models import PostCandidate, Source, SystemLog
from chief_editor.readiness import (
    ModeFlags,
    ReadinessItem,
    ReadinessReport,
    ReadinessSection,
)
from chief_editor.readiness.checks import (
    check_llm,
    check_mode,
    check_postiz,
    check_publishing_safety,
    check_reddit,
    check_sources,
    check_telegram_bot,
    check_telethon,
    check_vault,
    check_worker,
    compute_score,
    test_source,
)
from chief_editor.services.dry_run import compute_payload
from chief_editor.settings import get_settings
from chief_editor.time_utils import utcnow

from ..deps import get_session

router = APIRouter(prefix="/readiness", tags=["readiness"])


def _log(session: Session, event: str, message: str = "", level: str = "info", data: dict | None = None) -> None:
    session.add(
        SystemLog(level=level, event=event, message=message, data=data or {})
    )
    session.commit()


@router.get("", response_model=ReadinessReport)
def get_readiness(session: Session = Depends(get_session)) -> ReadinessReport:
    s = get_settings()
    sections: list[ReadinessSection] = []

    sections.append(ReadinessSection(key="mode", label="Mode", items=check_mode(s)))
    sections.append(
        ReadinessSection(key="llm", label="LLM", items=[check_llm(s, live=False)])
    )
    sections.append(
        ReadinessSection(
            key="telegram",
            label="Telegram",
            items=[check_telegram_bot(s, live=False), check_telethon(s, live=False)],
        )
    )
    sections.append(
        ReadinessSection(key="reddit", label="Reddit", items=[check_reddit(s, live=False)])
    )
    sections.append(
        ReadinessSection(key="postiz", label="Postiz", items=[check_postiz(s, live=False)])
    )
    sections.append(
        ReadinessSection(
            key="vault", label="Secrets vault", items=[check_vault(s)]
        )
    )
    sections.append(
        ReadinessSection(key="worker", label="Worker", items=[check_worker(session, s)])
    )
    sections.append(
        ReadinessSection(key="sources", label="Sources", items=check_sources(session, s))
    )
    sections.append(
        ReadinessSection(
            key="publishing_safety",
            label="Publishing safety",
            items=check_publishing_safety(s),
        )
    )

    score, label = compute_score(sections)
    return ReadinessReport(
        generated_at=utcnow(),
        mode=ModeFlags(
            app_env=s.app_env,
            mock_mode=s.mock_mode,
            demo_mode=s.demo_mode,
            live_mode=s.live_mode,
            dry_run_publish=s.dry_run_publish,
            publishing_enabled=s.publishing_enabled,
        ),
        sections=sections,
        overall_score=score,
        overall_label=label,
    )


# ---------------------------------------------------------------------------
# Per-integration live tests (safe / read-only)
# ---------------------------------------------------------------------------


@router.post("/test-llm", response_model=ReadinessItem)
def post_test_llm(session: Session = Depends(get_session)) -> ReadinessItem:
    item = check_llm(get_settings(), live=True)
    _log(session, "readiness.test_llm", item.message, data={"status": item.status})
    return item


@router.post("/test-telegram-bot", response_model=ReadinessItem)
def post_test_telegram_bot(session: Session = Depends(get_session)) -> ReadinessItem:
    item = check_telegram_bot(get_settings(), live=True)
    _log(session, "readiness.test_telegram_bot", item.message, data={"status": item.status})
    return item


@router.post("/test-telethon", response_model=ReadinessItem)
def post_test_telethon(session: Session = Depends(get_session)) -> ReadinessItem:
    item = check_telethon(get_settings(), live=True)
    _log(session, "readiness.test_telethon", item.message, data={"status": item.status})
    return item


@router.post("/test-reddit", response_model=ReadinessItem)
def post_test_reddit(session: Session = Depends(get_session)) -> ReadinessItem:
    item = check_reddit(get_settings(), live=True)
    _log(session, "readiness.test_reddit", item.message, data={"status": item.status})
    return item


@router.post("/test-postiz", response_model=ReadinessItem)
def post_test_postiz(session: Session = Depends(get_session)) -> ReadinessItem:
    item = check_postiz(get_settings(), live=True)
    _log(session, "readiness.test_postiz", item.message, data={"status": item.status})
    return item


@router.post("/test-source/{source_id}", response_model=ReadinessItem)
def post_test_source(
    source_id: str,
    session: Session = Depends(get_session),
) -> ReadinessItem:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    item = test_source(session, source, get_settings())
    _log(
        session,
        "readiness.test_source",
        item.message,
        data={"source_id": source.id, "status": item.status},
    )
    return item


@router.post("/dry-run-publish/{candidate_id}")
def post_dry_run_publish(
    candidate_id: str,
    platform: str = "telegram",
    session: Session = Depends(get_session),
):
    cand = session.get(PostCandidate, candidate_id)
    if cand is None:
        raise HTTPException(status_code=404, detail="candidate not found")

    payload = compute_payload(cand, platform)
    _log(
        session,
        "readiness.dry_run_publish",
        f"dry-run payload computed for candidate={cand.id} platform={platform}",
        data={
            "candidate_id": cand.id,
            "platform": platform,
            "body_length": payload["body_length"],
            "would_send": payload["would_send"],
        },
    )
    return {
        "ok": True,
        "preview": payload,
        "safety_note": (
            "This is a dry-run preview only. No external service was contacted."
        ),
    }
