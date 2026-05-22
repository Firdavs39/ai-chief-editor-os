"""Phase Q — regression baseline against REAL Kimi outputs.

R3's "Decagon regression set" principle, scaffolded. Locks in what the
detector says about two specific real-Kimi candidates (Phase 7 corp-psych
and Phase Q v1 conductor). Future prompt iterations must NOT regress
these scores — if they do, the test fails and we know.

This is the seed of a larger regression set (target: 50-200 verified
real candidates per workflow per R3).
"""
from __future__ import annotations

from chief_editor.services.generation.ai_tells import analyze

# ---------------------------------------------------------------------------
# Verbatim real Kimi outputs (preserved from .phase52/cand.json and
# .phase52/phaseq_arts.json). Treated as immutable golden inputs.
# ---------------------------------------------------------------------------

PHASE_7_CORP_PSYCH_TG_BODY = (
    "71% вакансий корппсихологов. 56% — выгорание. Это управленческий дефолт.\n\n"
    "По данным «Ясно» и Dream Job, спрос на корпоративных психологов вырос на 71% "
    "за два года. Параллельно 56% сессий приходится на выгорание, токсичность и "
    "переработки. Цифры растут синхронно — и это не совпадение.\n\n"
    "Компании массово нанимают психологов, но не меняют процессы. Переработки, "
    "давление, непрозрачные KPI — теперь «лечат» через сессии. Психолог в офисе "
    "становится пластырем: он гасит симптомы, пока система производит новые причины.\n\n"
    "Аудитория чувствует подмену. Люди перестают верить в корпоративную «заботу», "
    "когда границы не защищают, а ломают.\n\n"
    "Не пишите о балансе, если продукт или команда его не поддерживают.\n\n"
    "Проверьте свои процессы. Если команда выгорает, не заказывайте мотивационный "
    "постер — уберите причину."
)

PHASE_Q_V1_CONDUCTOR_TG_BODY = (
    "347 тысяч за сеньора, который смотрит. Это не найм. Это покупка зрителя.\n\n"
    "Если ты сейчас читаешь это в перерыве между ретро и планированием спринта, "
    "знай, что AI даёт десятикратное ускорение только в руках вовлечённого "
    "дирижёра, самого готового поправить партию агентов в реальном времени. "
    "Без вовлечённости дорогой инженер превращается в статиста с высоким окладом. "
    "Агенты крутятся и пишут код, а он ждёт, когда машина сама предложит вариант.\n\n"
    "Сначала думал, что дело в инструментах. Потом понял, что наоборот, инструменты "
    "работают, просто не на тех. Меня бесит, когда CFO называет это оптимизацией "
    "штата. Я не разбираюсь в симфонической музыке, но дирижёр без веры в "
    "собственный оркестр превращается в человека с палочкой, получающего деньги "
    "за натужные жесты у пустой консерватории.\n\n"
    "Вчера в кафе «Угол» на Пятницкой бариста Лёша за пять минут объяснил, почему "
    "их автоматическая кофемашина ломается: никто не моет группу после себя. Это, "
    "конечно, не про оркестр. Или про него?\n\n"
    "Ты можешь заменить конвейер джунов на сеньоров с зарплатой в 2,7 раза выше "
    "среднего по рынку и ждать волшебства, но когда вовлечённость на 23,4% ниже "
    "порога, агенты работают вхолостую. Цифры сдвигаются, а продукт стоит. "
    "Проверь свою команду на дирижёра."
)


# ---------------------------------------------------------------------------
# Phase 7 corp-psych baseline — observed detector reading
# ---------------------------------------------------------------------------


def test_phase_7_corp_psych_detector_baseline() -> None:
    """Locks in detector findings on the actual Phase 7 Kimi output.
    These flags are REAL — they describe genuine quality gaps Kimi
    produced. Future prompts must not regress (slop_count must stay
    ≤4) and may improve (slop_count = 0 = no detected tells)."""
    r = analyze(PHASE_7_CORP_PSYCH_TG_BODY)
    # Hook line opens fine — no Tier-1 tell
    assert r.tier1_in_opener is None
    # But em-dash density is too high (5.0 vs limit 3.5)
    assert r.em_dash_per_1000 > 3.5
    # And the anchors are integers (71%, 56%), not decimals — fails has_concrete_anchor
    assert r.has_concrete_anchor is False
    # First 100 chars opens with "71% вакансий корппсихологов." — no decimal/year/URL
    assert r.anchor_in_first_chars is False
    # The hook has screenshottable lines ("Это не найм." → no, that's Phase Q v1; let's check)
    # The lines are mostly longer; pattern-checks fine
    # Triple parallels: "Переработки, давление, непрозрачные KPI" + others
    assert r.triple_parallel_excess >= 2
    # Total slop should be in expected range (4 observed at baseline)
    assert 3 <= r.slop_count <= 5, f"unexpected slop_count: {r.slop_count}"


# ---------------------------------------------------------------------------
# Phase Q v1 conductor baseline — observed detector reading
# ---------------------------------------------------------------------------


def test_phase_q_v1_conductor_detector_baseline() -> None:
    """Phase Q v1 conductor candidate ("347 тысяч за сеньора"). The
    rich Phase Q v1 prompts produced visibly sharper output but still
    has detector flags. Locks in baseline."""
    r = analyze(PHASE_Q_V1_CONDUCTOR_TG_BODY)
    # No Tier-1 in opener
    assert r.tier1_in_opener is None
    # No em-dash flood (Kimi listened to evasion rule #9)
    assert r.em_dash_per_1000 <= 3.5
    # Has concrete anchor (2,7 раза, 23,4%) — Phase Q rules worked
    assert r.has_concrete_anchor is True
    # BUT — first 100 chars has "347 тысяч за сеньора" — no decimal, no year
    # The anchor is buried past 100 chars. Phase Q v7 should improve this.
    assert r.anchor_in_first_chars is False
    # Has screenshottable phrase ("Это не найм. Это покупка зрителя.")
    assert r.has_screenshot_phrase is True
    # The (post-fix) vague-time-markers list should be empty
    # (we removed "сейчас" which was a false-positive on this draft)
    assert r.vague_time_markers == [], f"unexpected vague markers: {r.vague_time_markers}"
    # No anti-CTA in opener/closer
    assert r.anti_cta_position is None
    # Total slop should be in expected range (3 observed at baseline)
    # — fewer flags than Phase 7 (which had em-dash flood + no anchor anywhere)
    assert r.slop_count <= 3, f"v1 should be cleaner than Phase 7 (got slop_count={r.slop_count})"


# ---------------------------------------------------------------------------
# Phase Q v1 > Phase 7 quality (the trim/research work delivered)
# ---------------------------------------------------------------------------


def test_phase_q_v1_strictly_better_than_phase_7_on_detector() -> None:
    """The Phase Q work was supposed to produce sharper output. The
    detector is the deterministic proxy for that. v1 must score ≤
    Phase 7 on slop_count (fewer flags = better)."""
    phase_7 = analyze(PHASE_7_CORP_PSYCH_TG_BODY)
    phase_q_v1 = analyze(PHASE_Q_V1_CONDUCTOR_TG_BODY)
    assert phase_q_v1.slop_count <= phase_7.slop_count, (
        f"Phase Q v1 ({phase_q_v1.slop_count} flags) should be ≤ Phase 7 "
        f"({phase_7.slop_count} flags). Quality regression."
    )


# ---------------------------------------------------------------------------
# Em-dash count specifically — the most-cited AI tell in 2026
# ---------------------------------------------------------------------------


def test_em_dash_phase_q_v1_dramatically_lower() -> None:
    """Phase 7 used 5.0 em-dashes/1000 (above the 3.5 limit). Phase Q v1
    used 0.0 — Kimi obeyed evasion rule #9. Locks in the improvement."""
    phase_7 = analyze(PHASE_7_CORP_PSYCH_TG_BODY)
    phase_q_v1 = analyze(PHASE_Q_V1_CONDUCTOR_TG_BODY)
    assert phase_q_v1.em_dash_per_1000 < phase_7.em_dash_per_1000
    assert phase_q_v1.em_dash_per_1000 < 3.5  # passing
    assert phase_7.em_dash_per_1000 > 3.5  # was failing
