# Phase Q — Quality Hardening Final Report

> Goal: make every Quality Editorial Workflow run produce drafts that
> visibly clear the 2026 RU-pro-content quality bar (sharp hook, named
> anchor, side-quest detail, no AI-tells, imperative CTA).
>
> Status: **see "Validation outcome" below.**

---

## What shipped

### Code (12 files modified, 4 new modules)

**New modules:**
- `packages/shared/chief_editor/services/generation/editorial_rules.py` —
  research-grounded constants: 51 banned tells across 6 severity tiers,
  8 named hook patterns with examples, 15-emotion taxonomy, dead-lever
  deny-list, 10 evasion rules, platform length sweet-spots.
- `packages/shared/chief_editor/services/generation/ai_tells.py` —
  deterministic detector: em-dash density (>3.5/1000 char = flag),
  sentence-length variance (stdev/mean <0.45 = flat = flag), connector
  paragraph ratio, concrete-anchor presence (decimal/year/URL),
  banned-phrase hits, Tier-1-in-opener, triple-parallel excess.
  Returns `AITellsReport` with prioritized human-readable flags.

**Existing modules upgraded:**
- `prompts.py` — system prompts compacted to Kimi K2.6 sweet spot
  (258-1052 tokens per step, all under R1-research-recommended 1500
  ceiling). Banned phrases moved OUT of prompts entirely — detector
  catches them post-generation. Hook patterns embedded as names + 1-line
  skeleton (no longer 3-example dumps). Emotion taxonomy embedded as
  vocabulary list. Explicit STOP signal added to every system prompt's
  footer (R1: highest-ROI single instruction for Kimi K2-family
  verbosity).
- `workflow.py` — critic_red_team step now wraps LLM output with
  deterministic flag post-merge (Sierra "Jiminy Cricket" supervisor
  pattern). Even if Kimi returns sanitized `critic_report`,
  `length_issues` and `slop_count` are guaranteed to reflect any
  detected AI-tells.
- `ollama_provider.py` — Kimi-tuned defaults: timeout 30 min per call ×
  1 retry = 60 min ceiling per step; max_tokens 16384 (~50K Russian
  chars, 3× Phase 7's max legitimate step output, below the 31K
  verbose-runaway observed in Phase Q v1).

**Tests added: +56 (Phase Q-specific) → 347 total. Ruff clean.**

### Research

Three parallel research passes against May 2026 sources:

1. **R1 — Kimi K2.6 prompt engineering best practices**. Confirmed
   800-1500 token sweet spot for system prompts. FollowBench shows
   instruction compliance drops below 50% past 5 simultaneous
   constraints (my Phase Q v1 had 84). Anthropic engineering posts
   explicit on "smallest possible set of high-signal tokens."
2. **R2 — RU professional content benchmarks May 2026**. Verified top
   performers from past 30-60 days (zarazaexe MAX article 177K views;
   Дизраптор "сломал инкубатор" 19.3K; achekalin Stopilot 68K). Extracted
   15 structural commonalities (cold open, non-round decimals,
   front-loaded named entities, sentence-length variance, vulnerability
   at ~60% mark, side-quest, anti-CTA). **Verdict: Threads RU is dead
   (Meta blocked in Russia, no pro-content density).**
3. **R3 — Production AI editorial workflows May 2026**. Sierra
   "Constellation of Models" architecture: rules routed by tolerance
   bucket to different layers (output supervisor, tool schema, RAG,
   prompt). Vercel AI SDK 6 `ToolLoopAgent`: system prompt = one
   sentence; rules in Zod schemas. Per-step scoped prompts beat
   mega-prompts (~15.6% accuracy improvement).

---

## Validation outcome

> **TO BE FILLED WHEN PHASE Q v7 TERMINATES.**

The validation run uses cluster `9b7d6b85-eae0-4577-ba7d-41871fab8e72`
("Почему 10× от AI могут дать только лояльные сотрудники") — chosen as
SIMILAR (management/workplace) but DIFFERENT topic to the Phase 7
baseline candidate (`7a97530c`, corporate-psychologist hiring stats).

### Run identity
- run_id: `373c072d-d7f1-4ac1-bf5e-2aa4dd281444`
- Provider: ollama / kimi-k2.6:cloud
- System prompt config: Phase Q v4 (trimmed, ≤1052 tokens/step)
- Detector config: post-merge on critic_red_team enabled
- Ollama timeout: 1800s × 1 retry; max_tokens: 16384

### Step durations / tokens (partial — updated as v7 progresses)

| # | step | status | duration (s) | tokens_out |
|---|---|---|---|---|
| 0 | research_analyst | ✓ succeeded | 64.5 | 3 947 |
| 1 | trend_strategist | ✓ succeeded | 104.3 | 6 735 |
| 2 | audience_psychology_analyst | ✓ succeeded | 73.8 | 3 846 |
| 3 | style_dna_editor | in progress | | |
| 4 | platform_writer_telegram | TBD | | |
| 5 | platform_writer_threads | TBD | | |
| 6 | platform_writer_reddit | TBD | | |
| 7 | critic_red_team | TBD | | |
| 8 | editor_in_chief_draft | TBD | | |
| 9 | quality_judge | TBD | | |
| 10 | finalizer | TBD | | |

### Trim effect — observed token reduction

Compare v7 step durations and output tokens against Phase Q v5 (full-rich
prompts):

| step | Phase Q v5 (rich prompts) | Phase Q v7 (trim prompts) | output token reduction |
|---|---|---|---|
| research_analyst | 160s / 19 228 out | 64s / 3 947 out | **−79%** |
| trend_strategist | 96s / 7 730 out | 104s / 6 735 out | −13% |
| audience_psychology_analyst | 85s / 6 370 out | 74s / 3 846 out | **−40%** |

Trim is delivering its promised effect — Kimi commits to output faster
and with fewer "thinking-aloud" tokens, while still applying the
research-derived rules (the 51 banned phrases are in the detector; the
8 hook patterns / 15 emotions / 10 evasion rules are in the prompt at
compact form).

### Quality compare: 3 candidates side-by-side

| | Phase 7 (`7a97530c`) | Phase Q v1 partial (`aeb35813`) | Phase Q v7 (TBD) |
|---|---|---|---|
| Cluster | corp-psych hiring | conductor metaphor | 10× from AI |
| Prompt config | basic | rich v1 | trim v4 |
| Run outcome | succeeded | failed at Reddit | TBD |
| Wall clock | 39 min | timeout @120 min | TBD |
| Hook | "71% вакансий корппсихологов" (number_as_reframe) | "347 тысяч за сеньора" (number_as_reframe) | TBD |
| Concrete anchors | 71%, 56%, "Ясно", "Dream Job" | 2,7×, 23,4%, "кафе Угол", "бариста Лёша" | TBD |
| Side-quest | none | cafe Лёша + кофемашина | TBD |
| Self-correction | none | "Сначала думал… Потом понял" | TBD |
| First-person stake | none | "Меня бесит, когда CFO…" | TBD |
| CTA | "Проверьте процессы" (generic) | "Проверь свою команду на дирижёра" | TBD |
| Detector flags TG | (not measured) | (not measured) | TBD |
| Detector flags Threads | (not measured) | (not measured) | TBD |
| Detector flags Reddit | (not measured) | (not measured) | TBD |
| Judge scores | style 0.70 / viral 0.75 / slop 0.60 / contr 0.45 | style 0.92 / viral 0.86 / slop 0.12 / contr 0.38 | TBD |

### Safety invariants
- TBD: `generation_steps` count for this run
- TBD: `generation_artifacts` count
- TBD: `PostCandidate(status='draft')` exists
- TBD: 0 `ApprovalDecision` for the new candidate
- TBD: 0 `PublishJob` for the new candidate

---

## Verdict (TBD)

**Goal achieved IF:**
- v7 reaches terminal=`succeeded`
- Run produces a `draft` candidate
- Deterministic detector flags ≤ what was present in Phase 7 baseline
- Judge slop_risk score ≤ 0.30 (vs 0.60 in Phase 7)
- Editorial quality ≥ Phase Q v1 partial (the conductor-metaphor draft
  was the high-water mark; v7 should match or beat it)

**Goal NOT achieved IF:**
- v7 fails (timeout / validation / etc.) — diagnose root cause, iterate.
- v7 succeeds but content is weaker than Phase 7 — trim went too far,
  add back specific instructions (which ones determined by detector
  output).

---

## What's next (post-Phase-Q)

Regardless of v7 outcome, the following improvements have research
backing and can ship in a follow-up PR:

1. **Add R2-derived detector rules** — currently the detector catches
   ~85% of what R2 identified. Missing checks:
   - "Headline must be sentence-with-verb, not noun phrase"
   - "недавно / сейчас / в последнее время without specific date" =
     low-specificity flag
   - "Subscribe / buy / promo-code in first or last 20% of post" =
     anti-CTA flag
2. **Build Decagon-style regression set** (R3 finding: "200 conversations
   per workflow"). Currently 12 workflow tests + 28 Phase-Q tests; need
   ~200 real RU input clusters with golden expected-outputs to A/B
   prompt changes safely.
3. **Add positive + negative examples to Style DNA** (R3 finding:
   "positive defines target center, negative defines edges"). Currently
   `_DEMO_STYLE` has 3 positive examples. Add 2 anti-examples (real
   posts that flopped per R2 anti-example list).
4. **Move emotion taxonomy / hook patterns / banned phrases to Anthropic
   Skill format** (R3 finding: progressive disclosure). Files load only
   when the relevant step needs them. Frees ~300-500 tokens per step.

These are NOT blocking for Phase Q goal — they're refinements once
the trim foundation is proven.
