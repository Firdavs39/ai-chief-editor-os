import asyncio

from chief_editor.collectors.mock import MockCollector
from chief_editor.models import Source


def test_mock_collector_returns_items() -> None:
    src = Source(kind="telegram", handle="@demo_channel", url="t.me/demo_channel", weight=7)
    items = asyncio.run(MockCollector().fetch(src, limit=10))
    assert len(items) >= 1
    first = items[0]
    assert first.body
    assert first.external_id
    assert first.posted_at is not None
    assert isinstance(first.engagement, dict)


def test_mock_collector_is_deterministic() -> None:
    src = Source(kind="reddit", handle="r/test", url="reddit.com/r/test", weight=6)
    a = asyncio.run(MockCollector().fetch(src))
    b = asyncio.run(MockCollector().fetch(src))
    assert [i.external_id for i in a] == [i.external_id for i in b]
