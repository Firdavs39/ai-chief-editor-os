from datetime import timedelta

from chief_editor.models import RawItem, StyleProfile
from chief_editor.services.trend_scoring import (
    engagement_score,
    novelty_score,
    recency_score,
    score_item,
    source_weight_score,
)
from chief_editor.time_utils import utcnow


def test_recency_decays_over_time() -> None:
    assert recency_score(0) == 1.0
    fresh = recency_score(1)
    stale = recency_score(48)
    assert fresh > stale
    assert 0 <= stale <= 1


def test_engagement_score_bounded() -> None:
    assert engagement_score({}) == 0.0
    s = engagement_score({"views": 50000, "shares": 800, "comments": 200})
    assert 0 < s <= 1


def test_source_weight_clamp() -> None:
    assert source_weight_score(0) == 0
    assert source_weight_score(5) == 0.5
    assert source_weight_score(99) == 1


def test_novelty_high_when_unseen() -> None:
    assert novelty_score("совершенно новая тема про космос", []) > 0.4
    assert novelty_score("совершенно новая тема", ["совершенно новая тема"]) < 0.2


def test_score_item_returns_full_breakdown() -> None:
    item = RawItem(
        source_id="s1",
        external_id="x",
        title="AI редактор контента",
        body="Тема AI редактора набирает обороты",
        url="",
        text_hash="h",
        engagement={"views": 5000, "shares": 80, "comments": 40},
        posted_at=utcnow() - timedelta(hours=2),
    )
    style = StyleProfile(
        name="default",
        tone="expert",
        audience="creators",
        target_topics=["AI и контент", "редактор"],
        example_posts=["AI редактор это умный соавтор"],
    )
    breakdown = score_item(item, source_weight=8.0, recent_cluster_reps=[], style=style)
    d = breakdown.as_dict()
    for key in (
        "recency", "engagement", "source_weight",
        "novelty", "controversy", "usefulness", "style_fit", "total",
    ):
        assert key in d
        assert 0 <= d[key] <= 1
