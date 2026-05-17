from chief_editor.services.critic import critique


def test_detects_ai_slop() -> None:
    notes = critique(
        tg_version="В эпоху технологий давайте погрузимся в новый тренд. Сохрани, попробуй сегодня.",
        threads_version="Стоит отметить важность этого момента.",
        cta="Сохрани, попробуй сегодня.",
        source_summary="источник про тренд",
        psychology_hook="давайте погрузимся",
    )
    checks = {n["check"] for n in notes}
    assert "ai_slop" in checks


def test_detects_weak_cta() -> None:
    notes = critique(
        tg_version="Никто не говорит вслух, но AI меняет редактуру. Конкретные цифры далее.",
        threads_version="Короткая мысль.",
        cta="это интересно",
        source_summary="тренд",
        psychology_hook="никто не говорит",
    )
    assert any(n["check"] == "weak_cta" for n in notes)


def test_detects_length_issue() -> None:
    long_tg = "Слово " * 300
    notes = critique(
        tg_version=long_tg,
        threads_version="ok",
        cta="Сохрани",
        source_summary="ok",
        psychology_hook="ok",
    )
    assert any(n["check"] == "length_issue" for n in notes)


def test_detects_copied_wording() -> None:
    source = "AI редактор меняет правила игры для русскоязычных авторов и команд."
    notes = critique(
        tg_version="AI редактор меняет правила игры для русскоязычных авторов и команд.",
        threads_version="ok",
        cta="Сохрани",
        source_summary=source,
        psychology_hook="ok",
    )
    assert any(n["check"] == "copied_wording" for n in notes)


def test_clean_post_no_high_severity() -> None:
    notes = critique(
        tg_version=(
            "Никто не говорит об этом вслух, но Threads начал давать преимущество "
            "русскоязычным авторам. Конкретно: вовлеченность выше Telegram на 28% за неделю."
        ),
        threads_version="Никто не говорит вслух: Threads даёт ru-авторам новый рост.",
        cta="Сохрани шаблон и попробуй адаптировать завтра.",
        source_summary="несколько каналов",
        psychology_hook="никто не говорит",
    )
    high = [n for n in notes if n["severity"] == "high"]
    assert high == []
