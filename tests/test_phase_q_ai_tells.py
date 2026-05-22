"""Phase Q (Quality Hardening) — deterministic AI-tells detector tests.

These tests pin down the floor-quality contract:
- Banned-phrase taxonomy is exhaustive and stable
- Deterministic metrics return correct numbers on known-good/known-bad input
- Aggregate report surfaces actionable flags in the right priority

The numbers are calibrated from research; bumping the thresholds in
editorial_rules.py without updating tests should fail loudly.
"""
from __future__ import annotations

from chief_editor.services.generation.ai_tells import (
    AITellsReport,
    analyze,
    analyze_drafts,
    banned_phrase_hits,
    connector_paragraph_ratio,
    em_dash_density,
    has_concrete_anchor,
    sentence_length_variance,
    tier1_in_first_sentence,
    triple_parallel_hits,
)
from chief_editor.services.generation.editorial_rules import (
    ALL_BANNED_TELLS,
    DEAD_LEVERS,
    EMOTION_TAXONOMY,
    EVASION_RULES,
    HOOK_PATTERNS,
    LENGTH_SWEET_SPOT,
)

# ---------------------------------------------------------------------------
# editorial_rules.py — taxonomy completeness
# ---------------------------------------------------------------------------


def test_banned_tells_contains_canonical_ai_phrases() -> None:
    """The phrases everyone agrees mark AI text must be present."""
    for phrase in (
        "в современном мире",
        "стоит отметить",
        "не секрет, что",
        "давайте погрузимся",
        "в заключение",
        "таким образом",
        "играет ключевую роль",
    ):
        assert phrase in ALL_BANNED_TELLS, f"missing canonical tell: {phrase!r}"


def test_banned_tells_no_duplicates_across_tiers() -> None:
    assert len(set(ALL_BANNED_TELLS)) == len(ALL_BANNED_TELLS), (
        "duplicate phrases across tiers — each tell should live in exactly one tier"
    )


def test_emotion_taxonomy_has_15_entries() -> None:
    """Locked-in count — research synthesis settled on 15 emotional states."""
    assert len(EMOTION_TAXONOMY) == 15


def test_emotion_taxonomy_entries_have_required_keys() -> None:
    for key, val in EMOTION_TAXONOMY.items():
        assert "ru_name" in val and val["ru_name"], f"{key}: missing ru_name"
        assert "when" in val and val["when"], f"{key}: missing 'when'"
        assert "opener_example" in val and val["opener_example"], (
            f"{key}: missing opener_example"
        )


def test_hook_patterns_has_8_entries_with_examples() -> None:
    assert len(HOOK_PATTERNS) == 8
    for key, val in HOOK_PATTERNS.items():
        assert "ru_name" in val
        assert "skeleton" in val
        examples = val.get("examples")
        assert isinstance(examples, tuple) and len(examples) >= 2, (
            f"{key}: needs at least 2 examples"
        )


def test_dead_levers_contains_known_burnt_out_patterns() -> None:
    """These were the canonical 'persuasion levers' that 2026 readers
    now read as marketing copy — the prompt must NEVER name them."""
    for dead in ("FOMO", "social proof", "curiosity gap", "scarcity"):
        assert dead in DEAD_LEVERS, f"missing dead lever: {dead!r}"


def test_evasion_rules_count_and_imperatives() -> None:
    """10 imperative rules, all in Russian."""
    assert len(EVASION_RULES) == 10
    for r in EVASION_RULES:
        assert isinstance(r, str) and len(r) > 20


def test_length_sweet_spots_match_research() -> None:
    """The numbers from research that drive prompt guidance."""
    assert LENGTH_SWEET_SPOT["telegram_body"] == (800, 1500)
    assert LENGTH_SWEET_SPOT["threads_body"] == (180, 380)
    assert LENGTH_SWEET_SPOT["reddit_title"] == (60, 90)


# ---------------------------------------------------------------------------
# ai_tells.py — individual deterministic checks
# ---------------------------------------------------------------------------


def test_em_dash_density_empty_and_safe() -> None:
    assert em_dash_density("") == 0.0
    assert em_dash_density("Текст без тире, только запятые. Всё ок.") == 0.0


def test_em_dash_density_flags_flood() -> None:
    # 10 em-dashes in ~100 chars = 100/1000 — way above limit
    text = "А — Б — В — Г — Д — Е — Ж — З — И — К — конец."
    density = em_dash_density(text)
    assert density > 3.5


def test_sentence_length_variance_safe_for_short_text() -> None:
    """<3 sentences → returns passing value to avoid false-flag."""
    assert sentence_length_variance("Одно предложение.") == 1.0


def test_sentence_length_variance_flags_flat_rhythm() -> None:
    """All 6-word sentences → variance is 0 → below 0.45."""
    text = ". ".join(["раз два три четыре пять шесть"] * 5) + "."
    v = sentence_length_variance(text)
    assert v < 0.45


def test_sentence_length_variance_passes_mixed_rhythm() -> None:
    """One short fragment + one long sentence + medium ones → passes."""
    text = (
        "Стоп. Сейчас покажу один пример, который я лично проверил на пяти "
        "разных каналах за прошлый месяц. Цифра удивит. Открой воронку — "
        "и посмотри, как ведёт себя конверсия после первой недели."
    )
    v = sentence_length_variance(text)
    assert v >= 0.45


def test_connector_paragraph_ratio_flags_flood() -> None:
    text = (
        "При этом важно понимать, что текст начинается так.\n\n"
        "Тем не менее, второй абзац — снова с коннектора.\n\n"
        "Однако третий тоже.\n\n"
        "Хороший четвёртый абзац без коннектора."
    )
    ratio = connector_paragraph_ratio(text)
    # 3 of 4 start with connector = 0.75 > 0.40
    assert ratio > 0.40


def test_connector_paragraph_ratio_passes_normal_text() -> None:
    text = (
        "Первый абзац начинается с конкретной сцены.\n\n"
        "Второй абзац продолжает мысль обычным языком.\n\n"
        "Третий абзац — личная реплика автора."
    )
    assert connector_paragraph_ratio(text) <= 0.40


def test_has_concrete_anchor_detects_decimal() -> None:
    assert has_concrete_anchor("76,3% пользователей отвалились на втором экране.") is True


def test_has_concrete_anchor_detects_year() -> None:
    assert has_concrete_anchor("В 2024 году мы переписали всё с нуля.") is True


def test_has_concrete_anchor_detects_url_and_handle() -> None:
    assert has_concrete_anchor("Подробнее на https://example.com") is True
    assert has_concrete_anchor("Спасибо @kabanova_writes за разбор") is True


def test_has_concrete_anchor_rejects_abstract_text() -> None:
    text = (
        "Многие компании сегодня сталкиваются с выгоранием сотрудников. "
        "Это серьёзная проблема, требующая внимания руководства."
    )
    # No decimal, no year, no @, no URL → no anchor
    assert has_concrete_anchor(text) is False


def test_banned_phrase_hits_returns_all_matches() -> None:
    # All phrases written exactly as they appear in the banned list.
    text = (
        "В современном мире, стоит отметить, что роль играет ключевую роль. "
        "Подводя итог: давайте погрузимся в эту тему вместе."
    )
    hits = banned_phrase_hits(text)
    assert "в современном мире" in hits
    assert "стоит отметить" in hits
    assert "играет ключевую роль" in hits
    assert "подводя итог" in hits
    assert "давайте погрузимся" in hits


def test_tier1_in_opener_detects_classic_ai_opener() -> None:
    """Opening with 'В современном мире' is the strongest AI tell."""
    text = "В современном мире технологии меняют всё. Дальше идёт обычный текст."
    hit = tier1_in_first_sentence(text)
    assert hit == "в современном мире"


def test_tier1_in_opener_returns_none_for_clean_opener() -> None:
    text = "76,3% продактов в выборке не пишут спецификации. Это симптом, а не лень."
    assert tier1_in_first_sentence(text) is None


def test_triple_parallel_hits_passes_normal_text() -> None:
    """Normal text with one trio in 600 words → within tolerance."""
    text = (
        "У нас в команде три человека — продакт, дизайнер и редактор. " * 1
        + "Дальше идёт длинный кусок текста без параллельных структур, "
        + "просто обычные предложения разной длины и формы. " * 30
    )
    assert triple_parallel_hits(text) == 0


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------


def test_aggregate_report_clean_draft_has_few_flags() -> None:
    """A draft with concrete anchor, varied rhythm, no banned phrases:
    no flags should fire."""
    # ~500 chars, 1 em-dash (within 3.5/1000 = ~2 em-dashes), concrete anchor (76,3% + 47).
    draft = (
        "76,3% продактов в выборке из 47 кампаний не пишут спецификации. "
        "Стоп. Это не лень, это структурный симптом. "
        "Когда у тебя нет времени на спеку, не пиши плохую — переписывай "
        "процесс согласования с командой. Я три месяца ходил по этим граблям "
        "и проверил на своей выборке. Цифры не врут, а вот выводы из них "
        "иногда выводят не туда. Это нормально, главное вовремя заметить."
    )
    rep = analyze(draft)
    assert rep.has_concrete_anchor is True, "76,3% should anchor"
    assert rep.tier1_in_opener is None
    assert rep.em_dash_per_1000 <= 3.5, f"got {rep.em_dash_per_1000}"
    # Slop count should be 0 — clean draft.
    assert rep.slop_count == 0, f"unexpected flags: {rep.flags}"


def test_aggregate_report_dirty_draft_fires_multiple_flags() -> None:
    """A draft that violates everything: tier-1 opener, no anchor, em-dash
    flood, banned phrases. All should surface."""
    draft = (
        "В современном мире — стоит отметить — компании играют ключевую роль "
        "в цифровизации — также важно понимать что это меняет рынок — "
        "и таким образом каждая компания должна — подводя итог — внедрить "
        "комплексный подход — открывающий новые горизонты."
    )
    rep = analyze(draft)
    assert rep.tier1_in_opener == "в современном мире"
    assert rep.em_dash_per_1000 > 3.5
    assert rep.has_concrete_anchor is False  # no decimals/years/URLs
    assert len(rep.banned_phrase_hits) >= 3
    # Slop count should be ≥ 4 (tier1 + em-dash + no-anchor + banned)
    assert rep.slop_count >= 4, f"only got flags: {rep.flags}"


def test_analyze_drafts_returns_report_per_platform() -> None:
    out = analyze_drafts(
        tg_body="Какой-то текст без тире.",
        threads_body="Короткий пост.",
        reddit_body="Длинный пост на reddit.",
    )
    assert set(out.keys()) == {"telegram", "threads", "reddit"}
    assert all(isinstance(v, AITellsReport) for v in out.values())


def test_report_flags_are_strings_under_240_chars() -> None:
    """Flags will be embedded in the critic_report — must fit length budget."""
    rep = AITellsReport(
        em_dash_per_1000=15.0,
        sentence_variance=0.1,
        connector_paragraph_ratio=0.9,
        has_concrete_anchor=False,
        banned_phrase_hits=["в современном мире", "стоит отметить", "таким образом"],
        tier1_in_opener="в современном мире",
        triple_parallel_excess=3,
    )
    for flag in rep.flags:
        assert isinstance(flag, str)
        assert len(flag) <= 240, f"flag too long ({len(flag)}): {flag!r}"


# ---------------------------------------------------------------------------
# Regression — current candidate quality
# ---------------------------------------------------------------------------


def test_current_candidate_quality_baseline() -> None:
    """Smoke check on the actual phase-7 candidate (7a97530c) Kimi output.
    Captures what Phase Q expects to improve.

    The body is the TG version of the candidate; this test documents
    what the deterministic detector says about it TODAY. If Phase Q
    improves the prompts, a follow-up validation run should produce a
    cleaner score on a NEW cluster.
    """
    tg_body = (
        "71% вакансий корппсихологов. 56% — выгорание. Это управленческий дефолт.\n\n"
        "По данным «Ясно» и Dream Job, спрос на корпоративных психологов вырос "
        "на 71% за два года. Параллельно 56% сессий приходится на выгорание, "
        "токсичность и переработки. Цифры растут синхронно — и это не совпадение.\n\n"
        "Компании массово нанимают психологов, но не меняют процессы. Переработки, "
        "давление, непрозрачные KPI — теперь «лечат» через сессии. Психолог в "
        "офисе становится пластырем: он гасит симптомы, пока система производит "
        "новые причины.\n\n"
        "Аудитория чувствует подмену. Люди перестают верить в корпоративную «заботу», "
        "когда границы не защищают, а ломают.\n\n"
        "Не пишите о балансе, если продукт или команда его не поддерживают.\n\n"
        "Проверьте свои процессы. Если команда выгорает, не заказывайте "
        "мотивационный постер — уберите причину."
    )
    rep = analyze(tg_body)
    # Has anchor (71%, 56%, "Ясно", "Dream Job") — though we'd want decimals
    # The current candidate IS reasonably clean against most deterministic checks.
    # This regression test fixes a snapshot we can compare against post-Phase-Q.
    assert rep.tier1_in_opener is None  # opener is fine
    # Em-dashes are present but not flooded — there are ~7 in this text
    # Length is ~1200 chars, so density ~6/1000 — ABOVE limit
    assert rep.em_dash_per_1000 > 3.5
