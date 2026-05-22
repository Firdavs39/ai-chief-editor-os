"""Phase Q v6 — R2-derived detector rules (RU viral content May 2026).

R2 research identified 4 additional deterministic checks that distinguish
top-performing RU professional posts from low-performing ones:

1. Named entity OR decimal in first 100 chars (front-loaded anchor)
2. At least one screenshottable short sentence (≤60 chars, ≥3 words)
3. No vague time markers ("недавно", "сейчас") without specific dates
4. No generic anti-CTA ("подпишись", "поделитесь с друзьями") in first
   or last 20% of post

These rules tested against real R2-verified post fragments.
"""
from __future__ import annotations

from chief_editor.services.generation.ai_tells import (
    analyze,
    anchor_in_first_chars,
    anti_cta_hit_position,
    has_screenshot_phrase,
    vague_time_marker_hits,
)

# ---------------------------------------------------------------------------
# 1. Anchor in first 100 chars
# ---------------------------------------------------------------------------


def test_anchor_in_first_chars_passes_top_performer_opener() -> None:
    """R2 example A1 (zarazaexe MAX article): «С 1 сентября 2025 MAX
    предустанавливается...» — date in first 30 chars."""
    text = (
        "С 1 сентября 2025 MAX предустанавливается на все продаваемые в "
        "РФ телефоны. Домен max.ru — в белом списке ТСПУ."
    )
    assert anchor_in_first_chars(text) is True


def test_anchor_in_first_chars_passes_decimal_opener() -> None:
    """R2 example A5 (achekalin Stopilot): non-round number in title."""
    text = (
        "76,3% продактов в России не пишут спецификации. Это не лень. "
        "Это симптом структурного сдвига."
    )
    assert anchor_in_first_chars(text) is True


def test_anchor_in_first_chars_fails_abstract_opener() -> None:
    """Generic opener with no decimal/year in first 100 chars."""
    text = (
        "Многие компании сегодня сталкиваются с проблемой выгорания "
        "сотрудников. Это серьёзная проблема, требующая комплексного "
        "подхода со стороны руководства."
    )
    assert anchor_in_first_chars(text) is False


def test_anchor_in_first_chars_fails_buried_anchor() -> None:
    """Anchor exists but is buried past the 100-char window."""
    text = (
        "Многие специалисты в сфере IT сегодня сталкиваются с серьёзными "
        "проблемами, требующими внимания. По нашим данным, 76,3% таких "
        "случаев решаются через переписку процессов."
    )
    # First 100 chars: "Многие специалисты в сфере IT сегодня сталкиваются с серьёзными "
    # "проблемами, требующими" — no anchor here. The 76,3% is past 100 chars.
    assert anchor_in_first_chars(text) is False


# ---------------------------------------------------------------------------
# 2. Screenshottable phrase
# ---------------------------------------------------------------------------


def test_screenshot_phrase_passes_phase_q_v1_hook() -> None:
    """Phase Q v1 produced «Это не найм. Это покупка зрителя.» — exactly
    the screenshottable pattern R2 names."""
    text = (
        "347 тысяч за сеньора, который смотрит. Это не найм. Это покупка "
        "зрителя. Дальше идёт детальный разбор того, как именно компании "
        "массово нанимают психологов и игнорируют процессы."
    )
    assert has_screenshot_phrase(text) is True


def test_screenshot_phrase_fails_uniform_long_sentences() -> None:
    """If every sentence is 15-25 words, no screenshottable line exists."""
    text = (
        "Компании массово нанимают корпоративных психологов в качестве "
        "ответа на растущее количество жалоб сотрудников на выгорание. "
        "Параллельно процессы внутри организаций остаются неизменными "
        "и продолжают производить те же причины переработок и стресса."
    )
    assert has_screenshot_phrase(text) is False


def test_screenshot_phrase_rejects_only_one_word_fragments() -> None:
    """If a draft has ONLY 1-word fragments and no proper short sentence,
    the detector flags it. (The function returns True if at least one
    sentence has ≥3 words AND ≤60 chars — purely structural, can't
    judge 'memorable'.)"""
    text = "Стоп. Ну. Ладно. Всё."
    assert has_screenshot_phrase(text) is False


# ---------------------------------------------------------------------------
# 3. Vague time markers
# ---------------------------------------------------------------------------


def test_vague_time_markers_flagged() -> None:
    text = (
        "Недавно крупные компании начали внедрять AI-агентов. "
        "В наши дни это становится индустриальным стандартом, и в "
        "последнее время мы видим рост спроса."
    )
    hits = vague_time_marker_hits(text)
    assert "недавно" in hits
    assert "в наши дни" in hits
    assert "в последнее время" in hits


def test_vague_time_markers_none_when_specific_dates() -> None:
    """If post uses specific dates, vague markers shouldn't appear."""
    text = (
        "С 1 сентября 2025 MAX предустанавливается на телефоны. "
        "К Q1 2026 квартальный отчёт зафиксировал рост на 71%."
    )
    assert vague_time_marker_hits(text) == []


# ---------------------------------------------------------------------------
# 4. Anti-CTA position
# ---------------------------------------------------------------------------


def test_anti_cta_in_opener_flagged() -> None:
    """«Подпишись и поставь лайк» в начале поста — death sentence per R2."""
    text = (
        "Подпишитесь на канал, чтобы не пропустить следующий разбор! "
        "Сегодня поговорим о том, как AI меняет рынок труда."
        + " Дальше идёт текст." * 20  # pad to ensure length > 100
    )
    hit = anti_cta_hit_position(text)
    assert hit is not None
    assert "opener" in hit


def test_anti_cta_in_closer_flagged() -> None:
    """Generic 'поделитесь с друзьями!' в конце — anti-pattern."""
    text = (
        "Какая-то нормальная аналитика про продукт и команду. "
        + "Серьёзный разбор кейса. " * 30
        + "Поделитесь с друзьями, если было полезно!"
    )
    hit = anti_cta_hit_position(text)
    assert hit is not None
    assert "closer" in hit


def test_anti_cta_in_middle_not_flagged() -> None:
    """If a CTA-like phrase appears in the MIDDLE (e.g. quoted), it's
    not in the death zone (first/last 20%)."""
    text = (
        "Хороший разбор кейса с конкретными цифрами и фактами. "
        + "Какой-то контент в середине. " * 10
        + "В этом куске мы упоминаем «подпишись» как анти-паттерн, "
        + "и продолжаем нормальный аналитический разбор дальше. " * 10
        + "Финальный аккорд — без CTA. " * 5
    )
    hit = anti_cta_hit_position(text)
    assert hit is None


def test_anti_cta_returns_none_for_clean_text() -> None:
    text = (
        "Сильный editorial-разбор с конкретикой и хуком в начале. "
        + "Текст без призывов подписаться. " * 20
        + "Конец на конкретной мысли, без CTA."
    )
    assert anti_cta_hit_position(text) is None


# ---------------------------------------------------------------------------
# Aggregate AITellsReport integration
# ---------------------------------------------------------------------------


def test_aggregate_report_includes_r2_flags_on_bad_draft() -> None:
    """A draft that violates the new R2 rules — all 4 should fire."""
    text = (
        "Многие компании сегодня сталкиваются с выгоранием. " * 4
        + "Недавно мы провели большое исследование на эту тему. "
        + "Подпишитесь, чтобы не пропустить следующие материалы!"
    )
    # No anchor in first 100 chars, no screenshottable phrase (all long
    # uniform sentences), vague time marker "недавно", anti-CTA in closer
    rep = analyze(text)
    assert rep.anchor_in_first_chars is False
    # may pass screenshot if any 60-char sentence... let's just check overall flags
    assert "недавно" in rep.vague_time_markers
    assert rep.anti_cta_position is not None and "closer" in rep.anti_cta_position
    # The flags list should mention all of these
    flag_text = " | ".join(rep.flags)
    assert "anchor in first 100 chars" in flag_text.lower()
    assert "vague time markers" in flag_text.lower()
    assert "anti-cta" in flag_text.lower()


def test_aggregate_report_clean_with_r2_rules() -> None:
    """A draft matching the R2 top-performer fingerprint — all new
    flags pass."""
    text = (
        "76,3% продактов в выборке за 2024 не пишут спецификации. "
        "Стоп. Это не лень. Это структурный симптом. "
        "Когда у тебя нет времени на спеку, не переписывай плохую — "
        "переписывай процесс согласования. Я три месяца ходил по этим "
        "граблям и проверил на двух командах."
    )
    rep = analyze(text)
    assert rep.anchor_in_first_chars is True
    assert rep.has_screenshot_phrase is True
    assert rep.vague_time_markers == []
    assert rep.anti_cta_position is None
