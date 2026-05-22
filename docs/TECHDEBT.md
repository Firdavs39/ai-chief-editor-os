# Technical Debt — discovered during Phase Q work

> Issues found during this session that are real but did NOT block
> the Phase Q delivery. Each has a brief description, severity, and
> recommended fix. Operator-visible behavior implications noted.

---

## TD-1. Worker thread collision: `generation_loop` vs `generation_runs_loop` ⚠️

**Severity:** medium. Slows Phase 5.2+ runs unpredictably. Does NOT
threaten safety.

**Symptom observed (Phase Q v7 run):**
- Phase 5.2+ workflow run on cluster `9b7d6b85` was advancing nicely
  (step 2 finished at 01:16:31 UTC).
- 57 seconds later (01:17:28), the legacy `generation_loop` fired its
  10-minute tick and called `generate_for_cluster(session, cluster)`
  on a different cluster (`d0b6e44f`) from demo seed.
- That sync Kimi call took the worker thread.
- Phase 5.2+ run sat idle waiting for worker availability for the
  duration of the legacy Kimi request (potentially up to the 30-min
  Ollama timeout).

**Root cause:**
The async worker in `apps/worker/worker/main.py` has two competing
loops:
1. `generation_loop` — the pre-Phase-2 worker that calls
   `generate_for_cluster` directly on top clusters (single-shot LLM
   per cluster). Runs every 600s. Intended for demo seed continuity.
2. `generation_runs_loop` — the Phase 2+ workflow advancer that ticks
   queued/running `GenerationRun` rows by one step per 75s. The "real"
   editorial pipeline.

Both end up on the same asyncio event loop. When `generate_for_cluster`
issues a sync Kimi call, it can block the loop for tens of minutes.

**Why this is technical debt:**
The legacy `generation_loop` was correct in the pre-Phase-2 world. In
the Phase 2+ world, the multi-step workflow IS the editorial pipeline.
Running both produces duplicate candidates from the same clusters AND
introduces worker-thread collisions.

**Recommended fix (two phases):**

A. **Quick win (one-line config):** set `GENERATE_INTERVAL_SECONDS`
   very high (e.g., 86400 = once per day) via `.env`. The legacy loop
   barely fires. Phase 5.2+ runs proceed without competition.

B. **Proper fix (one PR):**
   - In `generation_loop`, skip any cluster that has a `GenerationRun`
     with status in `{"queued", "running"}` in the last 24h. This
     prevents duplicate work and worker collisions.
   - Long-term: deprecate `generate_for_cluster` entirely and route
     "auto-generate top clusters" through `enqueue_run` + the workflow.

**Workaround for operator:** if Phase 5.2+ runs are taking longer than
expected, check `worker.log` for `generation_loop` activity. If you see
a "generating candidate for cluster=X via ollama" line with no follow-up
for >5 min, the legacy loop is blocking. Set
`GENERATE_INTERVAL_SECONDS=86400` and restart the worker.

---

## TD-2. "сейчас" false-positive in vague-time-marker detector (FIXED)

**Severity:** low (cosmetic — would have over-flagged some good drafts).

**Symptom:** the Phase Q v6 detector flagged "сейчас" in the phrase
«если ты сейчас читаешь это» as a vague-time-marker (R2-derived rule).
But that phrase is legitimate reader-temporal-deixis ("right now, as
you read"), not a date-replacement.

**Fix applied in commit `48b93ba`:** removed "сейчас" from
`VAGUE_TIME_MARKERS`. Distinguishing reader-deixis from
date-replacement requires NLP we don't have. Better to under-flag than
over-flag.

**Future:** if we want "сейчас" back, it needs context-aware detection
(only flag when used as sentence-leader replacing a date, e.g.,
"Сейчас компании внедряют..." but not "ты сейчас читаешь").

---

## TD-3. Kimi K2.6 "thinking-aloud" verbose-runaway under heavy prompts

**Severity:** high (caused 3 of 7 Phase Q validation runs to timeout
before max_tokens cap was tuned).

**Symptom:** with rich system prompts (~6000 chars / 2000 tokens), Kimi
generated 20-30K tokens of intermediate "thinking" before committing to
the final JSON. This:
- Drove individual step durations from ~5 min (Phase 7 baseline) to 30+ min.
- Caused API timeouts on the largest artifacts (Reddit body, editor-in-chief
  composite).
- Wasted ~$0.20 per failed run.

**Fix applied (Phase Q v3-v7):**
- `max_tokens=16384` cap on the Ollama provider (~3× normal output,
  catches verbose runaway without truncating).
- Explicit `STOP` signal in every system prompt's safety footer
  ("Верни строго один JSON-объект и СТОП").
- Prompt trim from ~2000 tokens to ~258-1159 tokens per step (R1 sweet
  spot 800-1500).

**Residual risk:** the cap can still truncate Kimi output if the
combined intermediate-thinking + final-JSON exceeds 16K tokens. If
seen in operator's logs as "invalid JSON twice" errors, bump
`OllamaProvider.DEFAULT_MAX_TOKENS` up by 4K. Or fix at the root by
moving prompts to even tighter Anthropic-skill-creator format.

---

## TD-4. No real LLM-as-judge regression set yet

**Severity:** medium (limits confidence in future prompt iterations).

**What's missing:** Decagon's published pattern is "200 verified
conversations per workflow" as a regression set that gates prompt
changes. We currently have:
- 366 unit tests (great coverage of code paths).
- 2 real Kimi candidates locked into `test_phase_q_real_kimi_baseline.py`
  as detector regression baselines (Phase 7 corp-psych + Phase Q v1
  conductor).

That's a long way from 200.

**Recommended:** build the regression set incrementally. Each successful
Phase 9+ daily publish becomes a "golden input" — log the cluster_id,
preserve the draft+detector-output, add to the regression test suite.
Within 60 days of daily-publish operation we'd have a useful 60-input
regression set.

---

## TD-5. Anti-CTA detector over-fires on `"подпишись"` in middle of paragraph

**Severity:** low.

**Status:** existing implementation only checks first/last 20%, so
this is already mitigated. Documented for completeness in case future
implementations widen the window.

---

## TD-6. Russian sentence tokenizer naïve

**Severity:** low (works well enough).

**Limitation:** the regex `(?<=[.!?…])\s+` splits on punctuation. Misses
some edge cases (abbreviations like "т.д.", "и.т.п.", quoted sentences).
Conservative — false negatives only (under-counts sentence boundaries).

**Recommended:** use stanza/spacy Russian model for proper sentence
segmentation IF the false-negative rate ever causes incorrect detector
verdicts. Not urgent.
