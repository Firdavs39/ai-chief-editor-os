"""Deterministic trend scoring. Every component is transparent."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

from ..models import RawItem, StyleProfile
from ..settings import get_settings
from ..time_utils import hours_since
from .dedup import jaccard, tokens

_CONTROVERSY_RU = {
    "скандал", "запрет", "конфликт", "обвинение", "увольнение", "санкции",
    "запретили", "блокировка", "критика", "осудили",
}
_CONTROVERSY_EN = {
    "controversy", "ban", "scandal", "fired", "lawsuit", "outrage", "leaked",
}


@dataclass
class ScoreBreakdown:
    recency: float
    engagement: float
    source_weight: float
    novelty: float
    controversy: float
    usefulness: float
    style_fit: float
    total: float

    def as_dict(self) -> dict[str, float]:
        return {
            "recency": round(self.recency, 3),
            "engagement": round(self.engagement, 3),
            "source_weight": round(self.source_weight, 3),
            "novelty": round(self.novelty, 3),
            "controversy": round(self.controversy, 3),
            "usefulness": round(self.usefulness, 3),
            "style_fit": round(self.style_fit, 3),
            "total": round(self.total, 3),
        }


def recency_score(hours: float, half_life: float = 18.0) -> float:
    if hours <= 0:
        return 1.0
    return float(math.exp(-math.log(2) * hours / half_life))


def engagement_score(raw: dict, baseline: float = 1000.0) -> float:
    score = 0.0
    score += float(raw.get("views", 0))
    score += float(raw.get("upvotes", 0)) * 5
    score += float(raw.get("reactions", 0)) * 3
    score += float(raw.get("comments", 0)) * 4
    score += float(raw.get("shares", 0)) * 6
    score += float(raw.get("forwards", 0)) * 6
    score += float(raw.get("replies", 0)) * 2
    if score <= 0:
        return 0.0
    return float(min(1.0, math.log1p(score) / math.log1p(baseline * 50)))


def source_weight_score(weight: float) -> float:
    return max(0.0, min(1.0, weight / 10.0))


def novelty_score(item_text: str, recent_cluster_reps: Iterable[str]) -> float:
    item_tokens = tokens(item_text)
    if not item_tokens:
        return 0.5
    best = 0.0
    for rep in recent_cluster_reps:
        best = max(best, jaccard(item_tokens, tokens(rep)))
    return float(max(0.0, 1.0 - best))


def controversy_score(text: str) -> float:
    norm = text.lower()
    ru_hits = sum(1 for w in _CONTROVERSY_RU if w in norm)
    en_hits = sum(1 for w in _CONTROVERSY_EN if w in norm)
    hits = ru_hits + en_hits
    if hits == 0:
        return 0.0
    return float(min(1.0, hits / 4.0))


def usefulness_score(text: str, target_topics: list[str]) -> float:
    if not target_topics:
        return 0.5
    item_tokens = tokens(text)
    target_tokens: set[str] = set()
    for topic in target_topics:
        target_tokens |= tokens(topic)
    if not target_tokens:
        return 0.5
    return float(jaccard(item_tokens, target_tokens) * 2.5)  # boost, then clamp


def style_fit_score(text: str, style: StyleProfile | None) -> float:
    if style is None or not style.example_posts:
        return 0.5
    item_tokens = tokens(text)
    sims = [jaccard(item_tokens, tokens(p)) for p in style.example_posts]
    if not sims:
        return 0.5
    return float(sum(sims) / len(sims) * 3.0)  # boost short overlaps


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_item(
    item: RawItem,
    source_weight: float,
    recent_cluster_reps: Iterable[str],
    style: StyleProfile | None,
) -> ScoreBreakdown:
    text = f"{item.title}\n{item.body}".strip()
    recency = recency_score(hours_since(item.posted_at))
    engagement = engagement_score(item.engagement or {})
    src_w = source_weight_score(source_weight)
    novelty = novelty_score(text, list(recent_cluster_reps))
    controversy = controversy_score(text)
    usefulness = _clamp01(
        usefulness_score(
            text,
            style.target_topics if style else [],
        )
    )
    style_fit = _clamp01(style_fit_score(text, style))

    weights = get_settings().score_weights
    total = (
        recency * weights["recency"]
        + engagement * weights["engagement"]
        + src_w * weights["source_weight"]
        + novelty * weights["novelty"]
        + controversy * weights["controversy"]
        + usefulness * weights["usefulness"]
        + style_fit * weights["style_fit"]
    )
    return ScoreBreakdown(
        recency=recency,
        engagement=engagement,
        source_weight=src_w,
        novelty=novelty,
        controversy=controversy,
        usefulness=usefulness,
        style_fit=style_fit,
        total=_clamp01(total),
    )


def score_cluster(items_with_weights: list[tuple[RawItem, float]],
                  recent_cluster_reps: Iterable[str],
                  style: StyleProfile | None) -> ScoreBreakdown:
    if not items_with_weights:
        return ScoreBreakdown(0, 0, 0, 0, 0, 0, 0, 0)
    breakdowns = [
        score_item(item, weight, recent_cluster_reps, style)
        for item, weight in items_with_weights
    ]
    return ScoreBreakdown(
        recency=max(b.recency for b in breakdowns),
        engagement=max(b.engagement for b in breakdowns),
        source_weight=max(b.source_weight for b in breakdowns),
        novelty=sum(b.novelty for b in breakdowns) / len(breakdowns),
        controversy=max(b.controversy for b in breakdowns),
        usefulness=max(b.usefulness for b in breakdowns),
        style_fit=sum(b.style_fit for b in breakdowns) / len(breakdowns),
        total=max(b.total for b in breakdowns),
    )
