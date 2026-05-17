from chief_editor.settings import Settings


def test_defaults_load() -> None:
    s = Settings(_env_file=None)
    assert s.app_env == "dev"
    assert s.mock_mode is True
    assert s.llm_provider == "mock"
    assert "recency" in s.score_weights


def test_capability_flags_false_without_keys() -> None:
    s = Settings(_env_file=None)
    assert s.has_anthropic is False
    assert s.has_openai is False
    assert s.has_telethon is False
    assert s.has_reddit is False
    assert s.has_telegram_publish is False
    assert s.has_postiz is False
