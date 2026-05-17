"""Generate PostCandidates from TrendClusters using the active LLM provider."""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session, select

from ..llm import get_llm_provider
from ..models import PostCandidate, RawItem, StyleProfile, TrendCluster, TrendSignal
from .critic import critique

log = logging.getLogger(__name__)

_CANDIDATE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "topic", "source_summary", "why_it_matters", "psychology_hook",
        "tg_version", "threads_version", "reddit_version", "cta",
        "style_match_score", "viral_score", "slop_risk", "controversy_risk",
        "recommendation",
    ],
    "properties": {
        "topic": {"type": "string"},
        "source_summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "psychology_hook": {"type": "string"},
        "tg_version": {"type": "string"},
        "threads_version": {"type": "string"},
        "reddit_version": {"type": "string"},
        "cta": {"type": "string"},
        "style_match_score": {"type": "number"},
        "viral_score": {"type": "number"},
        "slop_risk": {"type": "number"},
        "controversy_risk": {"type": "number"},
        "recommendation": {"type": "string", "enum": ["approve", "revise", "reject"]},
    },
}


def _system_prompt(style: StyleProfile | None) -> str:
    if style is None:
        return (
            "You are the AI Chief Editor. You write in Russian (ru-RU) by default. "
            "You craft sharp, expert content with a clear psychology hook and a strong CTA. "
            "You never invent facts. You output strict JSON."
        )
    banned = ", ".join(style.banned_phrases or [])
    examples = "\n---\n".join((style.example_posts or [])[:3])
    return (
        "You are the AI Chief Editor for the user's content brand. "
        f"Tone: {style.tone}. Audience: {style.audience}. "
        f"Language: {style.lang_primary} (write in this language). "
        f"Writing rules: {style.writing_rules}. "
        f"Banned phrases (avoid): {banned}. "
        f"Examples of the user's voice:\n{examples}\n"
        "You never invent facts. You output strict JSON only."
    )


def _user_prompt(cluster: TrendCluster, sample_text: str) -> str:
    keywords = ", ".join((cluster.keywords or [])[:6])
    return (
        f"тема: {cluster.representative_text[:140]}\n"
        f"keywords: {keywords}\n"
        f"score breakdown: {cluster.score_breakdown}\n"
        "Тексты-источники (объединённые):\n"
        f"{sample_text[:1800]}\n\n"
        "Сформируй пост-кандидат строго в JSON. "
        "tg_version ≤ 1024 символа. threads_version ≤ 500. reddit_version ≤ 1500."
    )


def generate_for_cluster(session: Session, cluster: TrendCluster) -> PostCandidate:
    style = session.exec(select(StyleProfile).where(StyleProfile.name == "default")).first()

    raw_items = session.exec(
        select(RawItem)
        .join(TrendSignal, TrendSignal.raw_item_id == RawItem.id)
        .where(TrendSignal.cluster_id == cluster.id)
        .limit(5)
    ).all()
    combined = "\n\n".join(f"{r.title}\n{r.body}".strip() for r in raw_items)

    provider = get_llm_provider()
    log.info("generating candidate for cluster=%s via %s", cluster.id, provider.name)
    payload = provider.complete_json(
        system=_system_prompt(style),
        user=_user_prompt(cluster, combined),
        schema=_CANDIDATE_SCHEMA,
    )

    notes = critique(
        tg_version=payload.get("tg_version", ""),
        threads_version=payload.get("threads_version", ""),
        cta=payload.get("cta", ""),
        source_summary=payload.get("source_summary", ""),
        psychology_hook=payload.get("psychology_hook", ""),
        controversy_keywords_hits=int(
            round(float(payload.get("controversy_risk", 0)) * 4)
        ),
    )

    candidate = PostCandidate(
        cluster_id=cluster.id,
        topic=payload.get("topic", cluster.representative_text[:120]),
        source_summary=payload.get("source_summary", ""),
        why_it_matters=payload.get("why_it_matters", ""),
        psychology_hook=payload.get("psychology_hook", ""),
        tg_version=payload.get("tg_version", ""),
        threads_version=payload.get("threads_version", ""),
        reddit_version=payload.get("reddit_version", ""),
        cta=payload.get("cta", ""),
        style_match_score=float(payload.get("style_match_score", 0.7)),
        viral_score=float(payload.get("viral_score", 0.6)),
        slop_risk=float(payload.get("slop_risk", 0.2)),
        controversy_risk=float(payload.get("controversy_risk", 0.1)),
        recommendation=payload.get("recommendation", "revise"),
        critic_notes=notes,
        status="draft",
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


def rewrite_candidate(
    session: Session,
    candidate: PostCandidate,
    mode: str,
    target: str,
) -> PostCandidate:
    provider = get_llm_provider()
    field_map = {"tg": "tg_version", "threads": "threads_version", "reddit": "reddit_version"}
    field_name = field_map.get(target, "tg_version")
    current = getattr(candidate, field_name) or ""
    new_text = provider.rewrite(current, mode) if current else current
    setattr(candidate, field_name, new_text)
    candidate.version += 1
    candidate.status = "revised" if candidate.status != "approved" else candidate.status
    candidate.critic_notes = critique(
        tg_version=candidate.tg_version,
        threads_version=candidate.threads_version,
        cta=candidate.cta,
        source_summary=candidate.source_summary,
        psychology_hook=candidate.psychology_hook,
        controversy_keywords_hits=int(round(candidate.controversy_risk * 4)),
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate
