"""Deterministic AI-tells detector for editorial drafts.

Phase Q (Quality Hardening). Complements the LLM critic step by running
fast, deterministic, language-aware checks on the three platform drafts
BEFORE the critic LLM is invoked. Results are merged into the critic's
`critic_report` artifact so the operator sees BOTH editorial judgement
AND mechanical AI-floor checks.

Why deterministic checks here, not in the LLM:
- Em-dash density, sentence-length variance, banned-phrase hits etc. are
  exactly the things the LLM critic is BAD at counting reliably.
- Cheap (no API call), reproducible, regression-testable.
- Forms a "quality floor" the LLM critic must explain its way around if
  the draft passes despite these flags.

Thresholds live in `editorial_rules.py` so they're a single source of truth.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .editorial_rules import (
    ALL_BANNED_TELLS,
    ANTI_CTA_PATTERNS,
    BANNED_TELLS_TIER_1,
    CONNECTOR_PARAGRAPH_RATIO_LIMIT,
    EM_DASH_PER_1000_LIMIT,
    FIRST_CHARS_ANCHOR_WINDOW,
    SCREENSHOT_PHRASE_MAX_CHARS,
    SCREENSHOT_PHRASE_MIN_WORDS,
    SENTENCE_START_CONNECTORS,
    SENTENCE_VARIANCE_MIN,
    TRIPLE_PARALLEL_LIMIT_PER_400_WORDS,
    VAGUE_TIME_MARKERS,
)

# ---------------------------------------------------------------------------
# Tokenisation helpers
# ---------------------------------------------------------------------------

# A "sentence" in Russian editorial text terminates with . ! ? or … followed
# by whitespace or end-of-string. Naïve regex — fine for our purposes; the
# checks are aggregate stats, not parse trees.
_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s+")

# Em-dash forms: real Unicode em-dash, en-dash, double-hyphen
# (Russian editors use the real em-dash; LLMs lean on it heavily).
_EM_DASH_RE = re.compile(r"[—–]|--")

# Concrete anchors that signal "this was written by someone who knows the topic":
#   - decimal numbers with comma or period ("76,3%", "1.5x", "12,4К")
#   - 4-digit years (1991, 2024)
#   - hashtags / @-handles
#   - URLs (any protocol)
#   - capitalised non-sentence-start tokens (very rough proper-noun signal)
_DECIMAL_RE = re.compile(r"\b\d+[,.]\d+")
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_HASHTAG_RE = re.compile(r"[#@]\w{2,}")
_URL_RE = re.compile(r"https?://\S+")

# Triple-parallel pattern (rough heuristic):
#   word(s), word(s) и word(s)    or
#   word(s), word(s), word(s)
# where each "word(s)" is 1-4 short tokens. Conservative — we only fire on
# clear symmetric trios so false-positives stay low.
_TRIPLE_RE = re.compile(
    r"\b(\w+(?:\s+\w+){0,3}),\s+(\w+(?:\s+\w+){0,3})(?:,\s+|\s+и\s+)(\w+(?:\s+\w+){0,3})\b",
    flags=re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = _SENTENCE_END_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _word_count(s: str) -> int:
    # Split on whitespace; drop empty.
    return sum(1 for w in re.split(r"\s+", s.strip()) if w)


def _paragraphs(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"\n\s*\n+", text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def em_dash_density(text: str) -> float:
    """Em-dashes per 1000 characters. Human baseline ~3.23. >3.5 = AI tell."""
    text = text or ""
    if not text:
        return 0.0
    hits = len(_EM_DASH_RE.findall(text))
    return hits / max(1, len(text)) * 1000


def sentence_length_variance(text: str) -> float:
    """stdev / mean of sentence word counts. Humans: 0.6-0.9. <0.45 = flat."""
    counts = [_word_count(s) for s in _sentences(text)]
    counts = [c for c in counts if c > 0]
    if len(counts) < 3:
        # Too short to judge — return a passing value so we don't false-flag.
        return 1.0
    mean = sum(counts) / len(counts)
    if mean == 0:
        return 0.0
    variance = sum((c - mean) ** 2 for c in counts) / len(counts)
    stdev = math.sqrt(variance)
    return stdev / mean


def connector_paragraph_ratio(text: str) -> float:
    """Fraction of paragraphs whose first sentence starts with an AI
    connector. >0.40 = mechanical flow."""
    paras = _paragraphs(text)
    if not paras:
        return 0.0
    hits = 0
    for p in paras:
        first_sentence = (p.lower().split(".", 1)[0] if p else "").strip()
        if any(first_sentence.startswith(c) for c in SENTENCE_START_CONNECTORS):
            hits += 1
    return hits / len(paras)


def has_concrete_anchor(text: str) -> bool:
    """Returns True iff the draft contains at least one specific anchor
    (decimal number, 4-digit year, hashtag, @-handle, or URL).

    Note: we deliberately do NOT count plain integers — "75%" is generic,
    "76,3%" is the kind of locatable-specificity humans use.
    """
    if not text:
        return False
    return bool(
        _DECIMAL_RE.search(text)
        or _YEAR_RE.search(text)
        or _HASHTAG_RE.search(text)
        or _URL_RE.search(text)
    )


def banned_phrase_hits(text: str) -> list[str]:
    """All Tier-1..6 banned phrases found in the draft (case-insensitive).
    Returns the list of HIT phrases for the critic to surface."""
    if not text:
        return []
    lower = text.lower()
    return [phrase for phrase in ALL_BANNED_TELLS if phrase in lower]


def tier1_in_first_sentence(text: str) -> str | None:
    """Returns the Tier-1 phrase if the FIRST sentence opens with one. None
    otherwise. Tier-1-in-opener is the strongest AI signal we measure."""
    sentences = _sentences(text)
    if not sentences:
        return None
    first = sentences[0].lower()
    for phrase in BANNED_TELLS_TIER_1:
        if first.startswith(phrase) or first.startswith(f"«{phrase}") or f" {phrase}" in first[:60]:
            return phrase
    return None


def anchor_in_first_chars(text: str, window: int = FIRST_CHARS_ANCHOR_WINDOW) -> bool:
    """Phase Q v6 (R2): top-performing RU posts have a named entity OR
    a decimal number within the first 100 characters. Reject if absent.
    Stronger than the global `has_concrete_anchor` check — the anchor
    must be UP-FRONT, not buried halfway down."""
    if not text:
        return False
    head = text[:window]
    return has_concrete_anchor(head)


def has_screenshot_phrase(text: str) -> bool:
    """Phase Q v6 (R2): top performers contain at least ONE short
    sentence (≤60 chars, ≥3 words) that can stand alone as a screenshot
    overlay. The "screenshottable line" hypothesis from R2 — viral RU
    posts are engineered around ONE memorable claim.

    Examples that pass: «Это не найм. Это покупка зрителя.»,
    «Конец эпохи 'через 200 метров направо'».
    """
    if not text:
        return False
    for s in _sentences(text):
        wc = _word_count(s)
        if wc >= SCREENSHOT_PHRASE_MIN_WORDS and len(s) <= SCREENSHOT_PHRASE_MAX_CHARS:
            return True
    return False


def vague_time_marker_hits(text: str) -> list[str]:
    """Phase Q v6 (R2): vague time markers ('недавно', 'сейчас', etc.)
    signal the writer didn't bother to cite a specific date. Top
    performers cite dates ('С 1 сентября 2025', 'Q1 2026'). Returns
    the list of vague markers FOUND."""
    if not text:
        return []
    lower = text.lower()
    return [m for m in VAGUE_TIME_MARKERS if m in lower]


def anti_cta_hit_position(text: str) -> str | None:
    """Phase Q v6 (R2 anti-example finding): generic subscribe/buy CTAs
    in the first or last 20% of a post correlate with low engagement.
    Returns 'opener' / 'closer' / None.

    Tier-1 anti-CTAs ("подпишись", "поделитесь с друзьями", etc.) in
    the wrong position are a hard floor flag — even good editorial work
    is sabotaged by ad-template CTAs."""
    if not text:
        return None
    n = len(text)
    if n < 100:
        return None
    head = text[: n // 5].lower()
    tail = text[-(n // 5):].lower()
    for cta in ANTI_CTA_PATTERNS:
        if cta in head:
            return f"opener: «{cta}»"
        if cta in tail:
            return f"closer: «{cta}»"
    return None


def triple_parallel_hits(text: str, per_400_words_limit: int = TRIPLE_PARALLEL_LIMIT_PER_400_WORDS) -> int:
    """Count of triple-parallel structures, normalised against 400-word baseline.

    Returns hits ABOVE the limit (0 means within tolerance). Conservative
    regex so false-positives stay low — only counts "X, Y, Z" or "X, Y и Z"
    where each token group is ≤4 words.
    """
    if not text:
        return 0
    raw_hits = len(_TRIPLE_RE.findall(text))
    words = _word_count(text)
    if words == 0:
        return 0
    # Scale: if we have 800 words, the limit is doubled.
    scaled_limit = int(per_400_words_limit * (words / 400)) if words > 100 else per_400_words_limit
    excess = raw_hits - scaled_limit
    return max(0, excess)


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------


@dataclass
class AITellsReport:
    """Per-draft deterministic AI-tells stats. Merged into critic_report."""

    em_dash_per_1000: float = 0.0
    sentence_variance: float = 0.0
    connector_paragraph_ratio: float = 0.0
    has_concrete_anchor: bool = False
    banned_phrase_hits: list[str] = field(default_factory=list)
    tier1_in_opener: str | None = None
    triple_parallel_excess: int = 0
    # Phase Q v6 (R2-derived):
    anchor_in_first_chars: bool = True   # passes by default
    has_screenshot_phrase: bool = True
    vague_time_markers: list[str] = field(default_factory=list)
    anti_cta_position: str | None = None

    @property
    def flags(self) -> list[str]:
        """Human-readable flag strings for the critic to surface. Each flag
        increments slop_count by 1. Capped at 6 flags so the critic_report
        list_size limit (3) plus our 3 isn't overwhelmed; we sort by severity.
        """
        out: list[str] = []

        # Severity 1 — instant AI tell, always surface
        if self.tier1_in_opener:
            out.append(
                f"Opener starts with banned Tier-1 tell: «{self.tier1_in_opener}» — replace."
            )
        if not self.has_concrete_anchor:
            out.append(
                "No concrete anchor (decimal number, year, named entity, URL) — "
                "draft reads as abstract."
            )

        # Severity 2 — mechanical AI patterns
        if self.em_dash_per_1000 > EM_DASH_PER_1000_LIMIT:
            out.append(
                f"Em-dash flood: {self.em_dash_per_1000:.1f} per 1000 chars "
                f"(limit {EM_DASH_PER_1000_LIMIT}) — replace most with commas/periods."
            )
        if self.sentence_variance < SENTENCE_VARIANCE_MIN:
            out.append(
                f"Flat sentence rhythm: stdev/mean = {self.sentence_variance:.2f} "
                f"(min {SENTENCE_VARIANCE_MIN}) — mix one short fragment and one long sentence."
            )

        # Severity 3 — looser patterns
        if self.connector_paragraph_ratio > CONNECTOR_PARAGRAPH_RATIO_LIMIT:
            out.append(
                f"Connector flood: {self.connector_paragraph_ratio*100:.0f}% of paragraphs "
                f"start with «при этом / тем не менее / однако» — limit "
                f"{CONNECTOR_PARAGRAPH_RATIO_LIMIT*100:.0f}%."
            )
        if self.triple_parallel_excess > 0:
            out.append(
                f"Too many symmetric triples («X, Y и Z»): {self.triple_parallel_excess} above limit."
            )

        # Banned phrase hits — surfaced as ONE flag listing top 3 hits
        if self.banned_phrase_hits:
            top = self.banned_phrase_hits[:3]
            extra = (
                f" (+{len(self.banned_phrase_hits) - 3} more)"
                if len(self.banned_phrase_hits) > 3
                else ""
            )
            out.append("Banned tells found: " + ", ".join(f"«{p}»" for p in top) + extra)

        # Phase Q v6 (R2-derived) — strong flags from top-performer fingerprint
        if not self.anchor_in_first_chars:
            out.append(
                "No anchor in first 100 chars — top performers front-load "
                "a named entity or non-round decimal number."
            )
        if not self.has_screenshot_phrase:
            out.append(
                "No screenshottable short sentence (≤60 chars, ≥3 words) — "
                "viral RU posts engineer ONE memorable line to be quoted."
            )
        if self.vague_time_markers:
            top = self.vague_time_markers[:2]
            out.append(
                "Vague time markers (use specific dates instead): "
                + ", ".join(f"«{m}»" for m in top)
            )
        if self.anti_cta_position:
            out.append(
                f"Generic anti-CTA detected at {self.anti_cta_position} — "
                f"top performers use anti-CTA or open question, not «подпишись»."
            )

        return out

    @property
    def slop_count(self) -> int:
        """How many of the flags should count toward critic_report.slop_count.
        Each flag is one slop point. The critic LLM can ADD to this from its
        own editorial reading; this is the floor."""
        return len(self.flags)


def analyze(text: str) -> AITellsReport:
    """Run all checks against one draft body and return the aggregate report."""
    return AITellsReport(
        em_dash_per_1000=em_dash_density(text),
        sentence_variance=sentence_length_variance(text),
        connector_paragraph_ratio=connector_paragraph_ratio(text),
        has_concrete_anchor=has_concrete_anchor(text),
        banned_phrase_hits=banned_phrase_hits(text),
        tier1_in_opener=tier1_in_first_sentence(text),
        triple_parallel_excess=triple_parallel_hits(text),
        # Phase Q v6 (R2-derived):
        anchor_in_first_chars=anchor_in_first_chars(text),
        has_screenshot_phrase=has_screenshot_phrase(text),
        vague_time_markers=vague_time_marker_hits(text),
        anti_cta_position=anti_cta_hit_position(text),
    )


def analyze_drafts(
    *,
    tg_body: str,
    threads_body: str,
    reddit_body: str,
) -> dict[str, AITellsReport]:
    """Convenience: run analysis over all three platform drafts."""
    return {
        "telegram": analyze(tg_body),
        "threads": analyze(threads_body),
        "reddit": analyze(reddit_body),
    }


__all__ = [
    "AITellsReport",
    "analyze",
    "analyze_drafts",
    "anchor_in_first_chars",
    "anti_cta_hit_position",
    "banned_phrase_hits",
    "connector_paragraph_ratio",
    "em_dash_density",
    "has_concrete_anchor",
    "has_screenshot_phrase",
    "sentence_length_variance",
    "tier1_in_first_sentence",
    "triple_parallel_hits",
    "vague_time_marker_hits",
]
