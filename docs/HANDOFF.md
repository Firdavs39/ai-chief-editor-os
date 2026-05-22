# Handoff — Phase 5.2 → Phase Q work completed by Claude

> What was actually shipped in this session, what's left for the operator
> (you), and the exact next action.

---

## 0. Phase Q (Quality Hardening) — added later in the session

After the original Phase 5.2-13 work, an additional **Phase Q** layer
was built on top. It addresses a separate concern: not "does the
system function?" (5.2 fixed that) but "is the output of a successful
run actually publishable?"

**Phase Q ships:**
- 51-phrase banned-tells catalogue across 6 severity tiers (in detector,
  NOT in prompts — frees tokens, catches more)
- 8 named hook patterns + 15-emotion taxonomy + 10 evasion rules +
  dead-lever deny-list embedded in system prompts at Kimi's sweet spot
  (258-1159 tokens per step)
- **Deterministic AI-tells detector** (`ai_tells.py`) with 11 checks:
  em-dash density, sentence-length variance, connector ratio,
  concrete-anchor presence, banned-phrase hits, Tier-1-in-opener,
  triple-parallel excess, **front-loaded anchor**, **screenshottable
  phrase**, **vague time markers**, **anti-CTA position**.
- Sierra-style supervisor: critic_red_team step's payload gets
  deterministic flags **merged AFTER** the LLM returns. Even if Kimi
  forgets to flag, Python guarantees the flags reach the operator.
- Kimi-tuned defaults: timeout 30 min × 1 retry, max_tokens 16384
  (3× normal output, catches verbose runaway without truncating).
- Bad/Good anti-example pair in writer prompts (R3 highest-ROI single
  intervention).
- 3 research passes (Kimi prompt engineering, RU viral benchmarks,
  production editorial workflows) — see `PHASE_5_2_REPORT.md` +
  `PHASE_Q_REPORT.md` for the full synthesis.

**Phase Q test count:** 362 (was 311 before Phase Q; +51 for the
Quality work on top of Phase 5.2-13's tests).

See `docs/PHASE_Q_REPORT.md` for the validation outcome on a real
Kimi run.

---

## 1. What was shipped — all phases that don't need operator credentials

### Phase 5.2 — Kimi stability hotfix ✅

**Code:**
- `packages/shared/chief_editor/services/generation/artifacts.py` —
  `editorial_rationale` cap 240 → 1500; content fields aligned to real
  platform limits (TG 4096, Threads 500, Reddit body 10K, Reddit title 300);
  metadata fields (`source_summary` / `why_it_matters` / `psychology_hook`)
  widened.
- `packages/shared/chief_editor/services/generation/prompts.py` —
  matching JSON-schema maxLength values; all 10 system prompts updated
  with explicit "≤1500 chars, public editorial summary, NOT
  chain-of-thought" phrasing; per-platform content guidance.
- `packages/shared/chief_editor/services/generation/workflow.py` —
  added validation-aware repair (one retry on non-length
  `ValidationError` only); length-overflow short-circuits to fail
  immediately (no silent truncation); structured `_build_repair_prompt`
  and `_summarize_validation_errors` helpers; per-step
  `generation.step.lengths` log line for length observability.

**Tests:** `tests/test_phase52_schema_and_repair.py` — 19 tests
covering: schema-vs-platform-limit lock (regression guard against
future maintainers raising limits past API limits), `_is_length_only_error`
classifier, `_summarize_validation_errors` safety, repair-on-non-length-error
end-to-end, repair-failure-still-safe, no-raw-prompt-in-artifact.

### Phase 6 — Provider fallback + token telemetry ✅

**Code:**
- `packages/shared/chief_editor/settings.py` — added
  `llm_provider_fallback: Literal["", "mock", "anthropic", "openai", "ollama"]`,
  default `""`.
- `packages/shared/chief_editor/llm/registry.py` — refactored to extract
  `_build_provider(name)` helper; added `get_fallback_llm_provider()`
  that returns the configured fallback or `None` (no-op default).
- `packages/shared/chief_editor/services/generation/workflow.py` —
  `_execute_llm_step` now wraps primary attempt with a fallback that
  fires only on NON-length validation errors (length overflows surface
  to the operator either way); returns `(payload, usage_dict)`.
- `packages/shared/chief_editor/llm/base.py` — token-usage primitives
  (`last_input_tokens`, `last_output_tokens`, `last_model`,
  `_record_usage`, `_reset_usage`).
- All four LLM providers (anthropic, openai, ollama, mock) updated to
  report usage.
- Workflow persists `tokens_in` / `tokens_out` to
  `GenerationStep` after every successful step.

**Tests:** `tests/test_phase6_fallback_and_telemetry.py` — 8 tests
covering: fallback fires on non-length error, fallback does NOT fire on
length-only error, fallback failure surfaces primary error, no-fallback
configured surfaces primary error, token usage persisted to step, mock
provider records approximate usage, full-mock-workflow regression,
fallback telemetry reflects the fallback provider.

**Operator-side script:** `scripts/phase6_batch.py` — enqueues N runs
back-to-back, polls each to terminal, writes a CSV report with
per-run outcome, step durations, and token totals. Refuses to start
if `PUBLISHING_ENABLED=true` or `DRY_RUN_PUBLISH=false`.

### Phase 7 — Real source collection scaffolding ✅

**Scripts:**
- `scripts/setup_rss_sources.py` — idempotently registers ~10 default
  RSS sources (vc.ru, Habr, TechCrunch, MIT TechReview, etc.). Zero
  credentials needed.
- `scripts/create_telethon_session.py` — interactive Telethon
  session-file builder. **Reads api_id + api_hash from Vault**, not
  from chat. Phone + SMS code go directly into Telethon over the
  encrypted Telegram protocol; Claude never sees them. Refuses to run
  if a session file already exists.

**Tests:** `tests/test_phase7_collector_safety.py` — 5 AST guard tests
that scan the actual collector source files and assert NO write-API
method is called (Telethon `send_message` / `edit_message` /
`delete_messages` / etc.; Reddit `submit` / `reply` / `upvote` / etc.).
Also asserts collectors never import publishers (layering invariant).

### Phase 8 — Safety rehearsal walker ✅

**Script:** `scripts/phase8_safety_walker.py` — interactive walker that
takes the operator through the 4-step publish ritual on a test channel,
verifying each gate transition in the DB. **The walker NEVER flips
`PUBLISHING_ENABLED` or `DRY_RUN_PUBLISH`** — those are operator
actions; the walker only inspects state and prompts for the next flip.

### Phase 10 — Token cost dashboard ✅

**Code:**
- `packages/shared/chief_editor/services/cost.py` — `PRICE_TABLE` keyed
  by `(provider, model)` (May 19 2026 prices for Anthropic Opus 4.7 /
  Sonnet 4.6 / Haiku 4.5 / Opus 4.1 / OpenAI / Ollama / mock);
  `usd_cost()`, `cost_per_run()`, `summary()` aggregating over the
  most-recent N runs.
- `apps/api/app/routers/analytics.py` — `GET /analytics/cost` endpoint
  returning per-run + grouped-by-provider + grouped-by-model totals.
  Defensive against raw-prompt leakage (no `prompt`/`response`/`raw`
  fields in any response).

**Tests:** `tests/test_phase10_cost.py` — 9 tests including unit cost
math, integration with the mock workflow, HTTP endpoint anti-leakage,
and a schema-stability guard.

### Phase 11 — Style DNA auto-learning scaffold ✅

**Code:** `packages/shared/chief_editor/services/style_learning.py` —
`propose_style_update()` that reads recent `published` candidates and
returns a `StyleProposal` (proposed changes only — NEVER mutates
`StyleProfile` silently). Capped at 30 source posts so a single biased
approval burst can't dominate. LLM-driven diff generation is stubbed
(deliberately) so the safety contract is testable now; the actual diff
prompt lands in a follow-up PR.

**Tests:** in `tests/test_phase11_phase12_scaffolds.py` — 4 tests
covering: no-published-history → no proposal; no-default-profile → no
proposal; proposal does NOT mutate profile; documented cap is 30.

### Phase 12 — Performance feedback scaffold ✅

**Code:** `packages/shared/chief_editor/services/performance_feedback.py` —
`record_view_snapshot()` (canonical `MetricSnapshot` schema);
`compute_engagement_boost_for_cluster()` (median views / baseline,
capped at `MAX_ENGAGEMENT_BOOST = 0.15`); `apply_engagement_boost()`
(mutates cluster `score_breakdown.engagement` but caps the FINAL value
at 1.0 so runaway boosts are impossible). Tracking window 14 days —
old snapshots ignored.

**Tests:** in `tests/test_phase11_phase12_scaffolds.py` — 6 tests
covering: documented cap, documented window, no-snapshots → 0 boost,
canonical schema persistence, cap-at-max even with absurd views, old
snapshots ignored.

### Phase 13 — Hosting decision documented ✅

**Doc:** `docs/HOSTING_DECISION.md` — three options (A: stay on home
machine + cloudflared; B: Fly.io single-container; C: Railway/Render)
with cost, uptime, effort, and a step-by-step Option-B deploy
procedure. Recommendation: **Option A through Phase 9, then evaluate**.
Pre-drafted `fly.api.toml` already in repo from earlier work.

### Cross-cutting

- **Two master docs** (`docs/PHASE_PLAN.md` and `docs/OPERATOR_RUNBOOK.md`)
  capture the roadmap and the exact 4-step publish ritual.
  These survive chat-context compaction so future sessions resume
  cleanly.
- **309 pytest pass, ruff clean** across all touched code.
- **No safety regressions.** `PUBLISHING_ENABLED=false`,
  `DRY_RUN_PUBLISH=true` defaults preserved. All publish-side tests
  (`test_publishing_safety.py`, `test_approval_gate.py`,
  `test_publishing_safety_http.py`) still pass.

---

## 2. What's left — operator-only steps

These are the steps Claude cannot do because the product's safety design
explicitly requires a human at each one. Total time: ~2.5 hours spread
over ~14 calendar days.

### Step A — Phase 5.2 re-run #2 (≤30 min, mostly waiting)

Run #1 on cluster `3d427f68` is currently in flight on Kimi. When it
reaches terminal:
- If `succeeded`: I'll enqueue run #2 on a different cluster automatically
  (poller will tell us); we expect both to succeed.
- If `failed`: read the error class. Length errors → no further action.
  Non-length → check whether the new validation-aware repair fired.

### Step B — Phase 6 reproducibility batch (0 min you + ~3.5 h Kimi runtime)

Product decision: **Kimi-only.** No second LLM provider. Phase 6 is a
pure stability test of the Phase-5.2 fix on Kimi over 8 different
clusters.

1. Tell me "run Phase 6 batch on Kimi" — I run
   `scripts/phase6_batch.py --n 8` against the running API.
2. ~3.5 hours of Kimi-time later, I produce a CSV report with
   success-rate, average wall-clock per run, token totals, and
   per-cluster outcomes.

The `LLM_PROVIDER_FALLBACK` setting in the codebase stays at its empty
default — it's a feature that exists but is not wired. If Kimi ever
becomes unreliable, that's a new decision, not pre-reserved
infrastructure.

### Step C — Phase 7 part 1: RSS (5 min you, hands-off after)

1. Tell me "wire RSS now" — I run `python -m scripts.setup_rss_sources`.
2. Within 10 minutes you'll see new `raw_items` rows from real feeds.

### Step D — Phase 7 part 2: Reddit (15 min you)

1. Register an app at https://www.reddit.com/prefs/apps (script type, no
   redirect URL).
2. POST `client_id` and `client_secret` to `/secrets/reddit/*`.
3. Tell me "reddit creds in vault" — I add 5 subreddits to the
   `sources` table.

### Step E — Phase 7 part 3: Telethon (45 min you)

1. Register an app at https://my.telegram.org (instant).
2. POST `api_id` and `api_hash` to `/secrets/telethon/*`.
3. ON YOUR MACHINE: `python -m scripts.create_telethon_session`. It
   prompts for phone + SMS code locally; Claude does not see them.
4. Tell me "telethon ready" — I add 5 public channels to the sources
   table and trigger the first read.

### Step F — Phase 8: safety rehearsal (30 min you)

1. Create disposable test channel `@chief_editor_test_<random>`.
2. Create bot via @BotFather, get `TELEGRAM_BOT_TOKEN`. Add bot as
   channel admin.
3. POST `bot_token` + `target_channel_id` to `/secrets/telegram/*`.
4. Approve one Phase 7 candidate in `/editor`.
5. Run `python -m scripts.phase8_safety_walker --candidate-id <id> ...`
   — it walks you through the 4 flag-flips, you do each one, walker
   verifies the gate in DB.
6. One test message appears in test channel. Walker tells you to revert
   flags. You revert.

### Step G — Phase 9: first production publish + 7-day observation (15 min × 7 days)

1. Decide on a real channel (new or existing). Add bot as admin. POST
   the new `target_channel_id`.
2. Every morning for 7 days:
   - Open `/trends`, pick a cluster.
   - Click Generate Brief, wait ~25 minutes.
   - Read draft in `/editor`. Approve / Reject / Rewrite.
   - On Approve: run the 4-step publish ritual from
     `docs/OPERATOR_RUNBOOK.md`.
3. After 7 days: subjective vote — is this useful? If yes, this is the
   "fully functional MVP" line. Phase 10+ continues from there.

---

## 3. The exact next action right now

You don't need to wait for Phase 5.2 run #1 to finish before doing
anything else. The fastest path forward:

1. **In parallel (0 min you)** — Tell me "run Phase 6 batch on Kimi" and
   "wire RSS now". Both can run in the background while you do other
   things. Within ~4 hours you have reproducibility data for Kimi AND
   real (non-demo) trend clusters in the dashboard.
2. **Tomorrow** — Reddit + Telethon credentials (Steps D + E).
3. **End of week** — Phase 8 rehearsal.
4. **Following Monday** — Phase 9 starts. Daily for 7 days.

After step 4 you have the product the original spec described.

**Kimi-only stack.** No second LLM provider is on the roadmap. If
Kimi-via-Ollama ever becomes unreliable, that's a fresh decision —
not pre-reserved insurance.

---

## 4. Sanity check: what's NOT done

- **Run #2 on a Phase 5.2 different cluster** — pending run #1 terminal.
- **Real LLM-driven `propose_style_update` prompt** (Phase 11 follow-up).
- **Per-channel engagement baseline** (Phase 12 follow-up; current
  baseline is hard-coded 1000 views).
- **Frontend cost-dashboard page** (`/analytics/cost` API exists; the
  React page is one more PR).
- **Production deploy on Fly** (configs ready; awaiting your decision).
- **First real publish on a production channel** (Phase 9 — operator
  task).

None of these block the "system functions" milestone. They become
priorities AFTER Phase 9 says the daily-publish habit works.

---

## 5. Files added/modified in this work

```
docs/PHASE_PLAN.md                                                     [new]
docs/OPERATOR_RUNBOOK.md                                               [new]
docs/HOSTING_DECISION.md                                               [new]
docs/HANDOFF.md                                                        [new — this file]

packages/shared/chief_editor/services/generation/artifacts.py          [modified — Phase 5.2]
packages/shared/chief_editor/services/generation/prompts.py            [modified — Phase 5.2]
packages/shared/chief_editor/services/generation/workflow.py           [modified — 5.2 + 6]
packages/shared/chief_editor/settings.py                               [modified — 6]
packages/shared/chief_editor/llm/base.py                               [modified — 6]
packages/shared/chief_editor/llm/anthropic_provider.py                 [modified — 6]
packages/shared/chief_editor/llm/openai_provider.py                    [modified — 6]
packages/shared/chief_editor/llm/ollama_provider.py                    [modified — 6]
packages/shared/chief_editor/llm/mock.py                               [modified — 6]
packages/shared/chief_editor/llm/registry.py                           [refactored — 6]
packages/shared/chief_editor/services/cost.py                          [new — 10]
packages/shared/chief_editor/services/style_learning.py                [new — 11 scaffold]
packages/shared/chief_editor/services/performance_feedback.py          [new — 12 scaffold]
apps/api/app/routers/analytics.py                                      [modified — 10 /analytics/cost]

scripts/phase6_batch.py                                                [new — 6]
scripts/setup_rss_sources.py                                           [new — 7]
scripts/create_telethon_session.py                                     [new — 7]
scripts/phase8_safety_walker.py                                        [new — 8]

tests/test_phase52_schema_and_repair.py                                [new — 19 tests]
tests/test_phase6_fallback_and_telemetry.py                            [new — 8 tests]
tests/test_phase7_collector_safety.py                                  [new — 5 tests]
tests/test_phase10_cost.py                                             [new — 9 tests]
tests/test_phase11_phase12_scaffolds.py                                [new — 10 tests]
tests/test_generation_workflow.py                                      [modified — stale 240-cap test updated]
```

Net diff:
- **+51 tests** (258 → 309).
- **0 safety regressions.**
- **All gates passing.**
