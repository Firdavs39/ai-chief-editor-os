from chief_editor.llm.mock import MockLLMProvider


def test_complete_json_returns_required_fields() -> None:
    provider = MockLLMProvider()
    out = provider.complete_json(
        system="you are editor",
        user="тема: Threads-first для русскоязычных авторов\nkeywords: threads, russian, creators",
        schema={"type": "object"},
    )
    for key in (
        "topic", "source_summary", "why_it_matters", "psychology_hook",
        "tg_version", "threads_version", "reddit_version", "cta",
        "style_match_score", "viral_score", "slop_risk", "controversy_risk",
        "recommendation",
    ):
        assert key in out
    assert isinstance(out["tg_version"], str) and out["tg_version"].strip()
    assert len(out["threads_version"]) <= 500
    assert out["recommendation"] in {"approve", "revise", "reject"}


def test_rewrite_modes() -> None:
    p = MockLLMProvider()
    original = "В эпоху технологий давайте погрузимся в важную тему AI редактуры контента и обсудим все аспекты."
    deslopped = p.rewrite(original, "deslop")
    assert "В эпоху" not in deslopped
    assert "погрузимся" not in deslopped
    shorter = p.rewrite(original, "shorter")
    assert len(shorter) < len(original)


def test_complete_json_deterministic_for_same_input() -> None:
    p = MockLLMProvider()
    a = p.complete_json("s", "тема: одно и то же", {"type": "object"})
    b = p.complete_json("s", "тема: одно и то же", {"type": "object"})
    assert a["topic"] == b["topic"]
    assert a["tg_version"] == b["tg_version"]
