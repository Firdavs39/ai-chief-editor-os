# Phase Plan — AI Chief Editor OS

> Master roadmap from Phase 5.2 (Kimi stability hotfix) to Phase 13
> (production deploy). Survives chat-context compaction.
>
> Convention: every phase has **Exit criteria** (when we know it's done) and
> **Kill criterion** (when to stop and change approach). Operator-only
> actions are explicitly marked.

---

## Status overview (snapshot)

| Phase | Status | Notes |
|---|---|---|
| 0 — Foundation MVP | ✅ done | dashboard, workflow, safety gates, demo seed |
| 5 — First real LLM (Ollama Kimi K2.6) | ✅ done | run `452341d4…` succeeded end-to-end |
| 5.1 — Reproducibility audit | ✅ done | run `63205283…` failed at `editorial_rationale > 240` |
| 5.2 — Kimi stability hotfix | 🔄 in flight | schema raised to platform-real, validation-aware repair added |
| 6 — Reproducibility batch + Anthropic fallback | ⏳ planned | needs ANTHROPIC_API_KEY in Vault |
| 7 — Real source collection | ⏳ planned | needs REDDIT_* + TELETHON_* + session-file |
| 8 — Safety rehearsal on test channel | ⏳ planned | needs TELEGRAM_BOT_TOKEN + test channel + operator flag-flips |
| 9 — First production publish | ⏳ planned | needs production channel + 7-day observation |
| 10 — Performance feedback loop | post-MVP | TG view-counts → scoring |
| 11 — Style DNA auto-learning | post-MVP | risky if not eval-gated |
| 12 — Token telemetry + cost dashboard | post-MVP | becomes critical at scale |
| 13 — Production hosting (off localhost) | post-MVP | needed only for 24/7 SLA |

---

## Phase 5.2 — Kimi stability hotfix

### Goal
Make the Quality Editorial Workflow robust to Kimi K2.6's verbosity tendencies without weakening any safety guarantee.

### Why
Phase 5.1 showed 1/2 runs failed because the schema cap on `editorial_rationale` was 240 chars — a UI-driven constraint that forced honest model output to be rejected as malformed. Loosening the schema is the right fix; clamping the model output silently is the wrong fix.

### Changes shipped
- `editorial_rationale` cap: 240 → **1500** across all 10 artifacts (`packages/shared/chief_editor/services/generation/artifacts.py`, `prompts.py`).
- Content fields now match **platform reality**:
  - `TelegramPostArtifact.body` / `FinalBriefArtifact.final_tg`: 1024 → **4096** (Telegram Bot API limit).
  - `TelegramPostArtifact.hook`: 80 → **160**.
  - `ThreadsPostArtifact.body` / `FinalBriefArtifact.final_threads`: **500** (unchanged — matches Threads).
  - `RedditPostArtifact.body` / `FinalBriefArtifact.final_reddit`: 1500 → **10000** (Reddit body soft cap).
  - `FinalBriefArtifact.source_summary`: 400 → **2000**.
  - `FinalBriefArtifact.why_it_matters`: 300 → **1500**.
  - `FinalBriefArtifact.psychology_hook`: 200 → **1500**.
- **Validation-aware repair** added in `_execute_llm_step`: on a NON-length Pydantic ValidationError (enum mismatch, missing field, score out of range, type mismatch), one targeted retry is made with a structured repair prompt. Length errors are NOT retried — the schema now matches reality and a length overflow is a genuine content problem the operator must see.
- **Length observability** via `log.info("generation.step.lengths step=... lengths={...}")` after every successful step. Field lengths only, never values.
- 19 new tests in `tests/test_phase52_schema_and_repair.py` covering: schema-vs-platform-limit lock (test guards future maintainers from raising limits past API limits), `_is_length_only_error` classifier, `_summarize_validation_errors` safety, repair-on-non-length-error end-to-end, repair-failure-still-safe, no-raw-prompt-in-artifact regression.

### Exit criteria
- ✅ 277 pytest pass (was 258 + 19 new)
- ✅ ruff clean
- 🔄 Re-run cluster `3d427f68-4b02-42a2-96ff-e874b1fe3342` (the Phase 5.1 failed cluster) on real Kimi → **succeeded**
- ⏳ Run #2 on a different cluster → **succeeded**
- ⏳ Both runs produce 11 steps, 11 artifacts, 1 PostCandidate(status=draft), 0 ApprovalDecision (for this candidate), 0 PublishJob (for this candidate)
- ⏳ `publishing_enabled=false` and `dry_run_publish=true` throughout

### Kill criterion
If both runs fail at the same step with the same non-length error → Kimi has a deeper compliance problem. Pause, escalate, consider promoting Sonnet to primary in Phase 6.

---

## Phase 6 — Reproducibility batch (Kimi-only)

### Goal
Establish a real failure-rate baseline for Kimi K2.6 over 8 different clusters with the Phase 5.2 schema fix in place.

### Product decision
**Kimi-only.** We do not bring in a second LLM provider in this alpha. The `LLM_PROVIDER_FALLBACK` setting shipped in Phase 6 is dormant by default (empty string) and is intentionally not wired to any second provider. If Kimi ever becomes unreliable enough to need backup, that becomes a new phase with a new decision — it is NOT pre-reserved infrastructure.

### Operator-action gates ⚠️
- **None.** Uses the already-configured Ollama/Kimi credentials in the Vault.

### Implementation scope (Claude does — already shipped in this session)
1. **`LLM_PROVIDER_FALLBACK` setting** (shipped) in `packages/shared/chief_editor/settings.py`: `Literal["", "anthropic", "openai", "ollama"]`. Default empty — fallback never fires unless operator opts in. When set, a step-level failure on the primary triggers ONE retry on the fallback for THAT step only.
2. **`scripts/phase6_batch.py`** (shipped): enqueues runs on N clusters back-to-back, polls each to terminal, writes a CSV report with run_id, cluster_id, status, step_reached, duration_sec, error_class, tokens_in_total, tokens_out_total. Refuses to launch unless `PUBLISHING_ENABLED=false` and `DRY_RUN_PUBLISH=true`.
3. **Cost telemetry hook** (shipped) in providers: every `complete_json` records tokens_in / tokens_out into the existing `GenerationStep.tokens_in/out` columns. NO API call goes uncounted from this phase forward.

### Exit criteria
- Kimi failure-rate < 10% over the 8-cluster batch.
- Per-step token counts populated for all new runs.
- Cost-per-run documented for Kimi.

### Kill criterion
If Kimi failure-rate ≥ 50% even after Phase 5.2 → stop, escalate to product owner. The decision to introduce a second LLM is NOT pre-made; it's a fresh call based on what specifically broke.

### Decision point ⚠️
Estimated cost of the 8-run batch on Kimi via Ollama Cloud: **~$0.50–$2.00 total**. Claude will ask before launching. You approve the spend.

---

## Phase 7 — Real source collection

### Goal
Replace `demo/seed` with actual signal flow from real RSS feeds, Reddit subreddits, and public Telegram channels.

### Operator-action gates ⚠️
- **You provide `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET`** via `POST /secrets/reddit/*`.
- **You provide `TELETHON_API_ID` + `TELETHON_API_HASH`** via `POST /secrets/telethon/*`.
- **You generate the Telethon session file ON YOUR MACHINE** via the interactive `python -m scripts.create_telethon_session` (which I'll provide). It triggers a phone-SMS code from Telegram; you type it locally. The session file lives in `data/telethon/` and is mounted by the worker.
- **You decide which 5 TG channels to monitor** (must be publicly readable; bot is NOT required for read).

### Implementation scope (Claude does)
1. **`scripts/setup_rss_sources.py`**: idempotent script that registers ~10 RSS feeds (TechCrunch, vc.ru, Habr top, marketing-news, etc.) in the `sources` table. Zero-credentials.
2. **`scripts/create_telethon_session.py`**: interactive session-builder. Prompts you for phone, accepts SMS code, writes the encrypted session file. **Refuses to log the code or the phone number.**
3. **Source configuration UI in `/sources`**: form to add/remove RSS feeds, list Reddit subreddits, list Telegram channel handles. Reads/writes the `sources` table. No credential editing here — that goes through the Vault page.
4. **Collector hardening**:
   - RSS: respect ETag / Last-Modified headers, exponential backoff on 429.
   - Reddit: official `asyncpraw` only, read scopes only, single connection pool.
   - Telethon: low poll rate (15 min minimum), graceful flood-wait handling, NO send/edit/delete API calls anywhere in the codebase (AST guard test).
5. **`tests/test_collectors_safety.py`**: AST guard tests that Telethon code never calls `send_message`, `edit_message`, `delete_messages`, etc. Reddit code never calls `submit`, `reply`, `vote`.

### Exit criteria
- ≥3 source types active with rows in `raw_items` within 24 h.
- ≥1 organic trend cluster (not from seed) appears in `/trends`.
- 0 Telethon `FloodWaitError` events for ≥24 h.
- AST guards pass: NO write-API surface in collectors.

### Kill criterion
If Telethon hits FloodWaitError within 24 h → drop Telegram collection, run on RSS+Reddit only, revisit after 7 days with poll-interval ≥60 min.

### Decision point ⚠️
Before launch: which 5 TG channels do you want? They must be PUBLIC and you should have the legal right to read+republish summaries.

---

## Phase 8 — Safety rehearsal on a test channel

### Goal
Prove the entire publish path works end-to-end on a sacrificial Telegram channel, with all 3 safety gates verified live.

### Operator-action gates ⚠️
- **You create a test channel** (e.g. `@chief_editor_test_$(random)`). Disposable, no real audience.
- **You create a Telegram bot via @BotFather**, get `TELEGRAM_BOT_TOKEN`. Add the bot as channel admin.
- **You provide `TELEGRAM_BOT_TOKEN` + `TELEGRAM_TARGET_CHANNEL_ID`** via `POST /secrets/telegram/*`.
- **You flip the safety flags at each step** — Claude only inspects DB state and tells you when it's safe to proceed to the next flip. **Claude never flips `PUBLISHING_ENABLED` or `DRY_RUN_PUBLISH`.** This is the product safety contract.

### Implementation scope (Claude does)
1. **`scripts/phase8_safety_walker.py`**: interactive script that walks you through the 4-step ritual:
   1. Approve candidate → verify `PublishJob.status='pending'`.
   2. Worker tick with both flags off → verify `status='blocked'`. Print exact SQL to run.
   3. WAIT FOR YOUR INPUT to flip `PUBLISHING_ENABLED=true`. Worker tick → verify `status='dry_run'`, print `PublishResult.payload`.
   4. WAIT FOR YOUR INPUT to flip `DRY_RUN_PUBLISH=false`. Worker tick → verify `status='running' → 'done'`. Print Telegram message URL.
   5. ASK YOU TO REVERT both flags.
2. **`docs/OPERATOR_RUNBOOK.md`**: the same ritual as a one-page checklist (≤200 lines, printable).
3. **`tests/test_phase8_safety_walker.py`**: unit-level coverage that the walker never advances state on its own, only asks the operator.

### Exit criteria
- One real Telegram message visible in the test channel.
- Each gate transition verified in DB with row-level evidence.
- Runbook committed.
- `PUBLISHING_ENABLED` reverted to `false` and `DRY_RUN_PUBLISH` reverted to `true` at end of session.

### Kill criterion
If a message arrives in the test channel WITHOUT a corresponding operator-initiated flag flip → safety bug. **Halt all work.** Diagnose. Fix. Re-test. Do not proceed to Phase 9 until reproduced safely.

---

## Phase 9 — First production publish

### Goal
One real channel, one approved post per day, monitored for 7 days. This is the "fully functional MVP" milestone.

### Operator-action gates ⚠️
- **You choose the production channel** (new or existing, your decision).
- **You add the same bot OR a new bot as admin** to the production channel.
- **You provide `TELEGRAM_TARGET_CHANNEL_ID`** for production. Test channel id stays available as fallback.
- **You run the runbook (Phase 8 ritual) ONCE per approved post**, daily, for 7 days.
- **You make the editorial decisions** — approve/reject/rewrite — and accept full editorial responsibility for what gets published. Claude is a tool, not the editor.

### Implementation scope (Claude does)
1. **Daily approval-prep email** (optional, off by default): at a configured time each morning, the API sends an email-or-Telegram-DM to the operator with: "N new candidates pending, top cluster: ..., quick-link: ...".
2. **Approval analytics**: track time-to-approval, approval-rate, reject-rate by step (which steps consistently lead to `revise` recommendations). Surface in `/analytics`.
3. **Incident-log table** (`publish_incidents`): captures any deviation (wrong post sent, double-publish, gate bypass attempt). Defense-in-depth.

### Exit criteria (after 7 days)
- ≥3 posts published.
- Operator subjective: «это полезно» / «это не полезно» (Claude asks explicitly).
- 0 incidents in `publish_incidents`.
- approval-rate ≥ 25% (else Phase 6.1 prompt engineering needed).

### Decision points after Phase 9 (operator decides)
- **"Works"** → start Phase 10 (analytics feedback loop).
- **"Editorial quality bad"** → Phase 6.1 (prompt re-engineering OR model swap).
- **"Workflow clunky"** → Phase 7.1 (UX polish on approval flow).

This is the MVP-done line.

---

## Phase 10 — Performance feedback loop

### Goal
Use real engagement (TG view counts, reactions, replies) to inform future trend scoring and editorial decisions.

### Implementation scope
1. **TG view-count collector**: every published post is checked daily for 14 days; views recorded in `metric_snapshots`.
2. **Reaction / reply scraping** (where available via Bot API).
3. **Engagement-aware trend scoring**: clusters whose past published posts performed well get a boost in `score_breakdown.engagement`. Limit boost magnitude so it doesn't create runaway feedback.
4. **`/analytics` dashboards** updated with engagement timelines per cluster, per source.

### Exit criteria
- ≥2 weeks of engagement data collected.
- Scoring formula updated with engagement boost capped at 0.15 of total score.
- `/analytics` page shows engagement timelines.

### Kill criterion
If the engagement boost creates a runaway loop (same topic re-published constantly) → cap the boost lower or add cooldown periods.

---

## Phase 11 — Style DNA auto-learning

### Goal
Auto-update the `style_profile` based on what gets approved AND performs well.

### Risk
**Can drift to whatever the operator over-approves.** A single biased approval session could permanently change the voice. Solution: every auto-update is a PROPOSAL that the operator reviews in `/style-dna` before it becomes active.

### Implementation scope
1. **Style-extraction service**: takes the last N approved+published posts, runs them through a style-summarization prompt (Haiku), proposes updates to `style_profile.writing_rules` and `banned_phrases`.
2. **`/style-dna` page** shows current profile vs proposed changes side-by-side with diff highlighting.
3. **Operator clicks Accept / Reject per proposal**. No silent style-mutation.
4. **`tests/test_style_dna_safety.py`**: assert that style profile NEVER changes without an explicit `StyleProfileChangeApproval` row.

### Exit criteria
- One round of operator-approved style updates ships and shows up in next generation's output.
- AST guard test passes.

### Kill criterion
Skip this phase if Phase 9 reveals the operator doesn't actually want voice automation. Manual style tuning may be fine.

---

## Phase 12 — Token telemetry + cost dashboard

### Goal
Surface real cost data so the operator can see where the money goes.

### Implementation scope
1. **Already added in Phase 6**: tokens_in / tokens_out per `GenerationStep`.
2. **Cost-per-token table** in `settings.py` keyed by `(provider, model)` — kept in sync with current pricing.
3. **`/analytics/cost`** page: cost per run, cost per cluster, daily/weekly totals, provider breakdown, projection for next 30 days.
4. **Cost alarms**: when daily cost exceeds a configurable threshold, write an `IncidentLog` row and (optionally) email the operator.

### Exit criteria
- Cost-per-run accuracy within ±20% of provider invoice (cross-check after 1 week).
- Operator can answer "how much did I spend last week?" in 1 click.

### Kill criterion
If accuracy <80% → check tokenizer mismatches (Opus 4.7's tokenizer changed in May 2026). Recalibrate.

---

## Phase 13 — Production hosting

### Goal
Move off `localhost + cloudflared` to a real hosting target.

### Decision point ⚠️
**Where do you want to host?**
- **Option A — Fly.io**: configs already drafted (`fly.api.toml`, `fly.worker.toml`). Free tier insufficient; expect $20–50/mo for api+worker+postgres+redis. Easiest path given existing configs.
- **Option B — Railway**: simpler one-click, but stateless workers awkward. ~$15–40/mo.
- **Option C — Stay on home machine + cloudflared**: keep current setup. Cost: $0. Risk: home machine downtime = product downtime. Fine for one operator.

### Implementation scope (assuming Fly.io)
1. **Verify `fly.api.toml`, `fly.worker.toml`** for May 2026 Fly defaults (some platform features changed since the original drafts).
2. **Managed Postgres**: provision via `fly pg create` (note: this is the Fly billing gate that blocked earlier; needs payment method).
3. **Secrets migration**: `MASTER_ENCRYPTION_KEY`, `ADMIN_TOKEN`, etc. moved from local `.env` to `fly secrets set`. Vault entries are encrypted-at-rest so they stay in Postgres.
4. **DNS + TLS**: cloudflared replaced by fly.dev domain or custom domain.
5. **Worker singleton**: ensure only ONE worker instance runs at a time (multiple workers would create duplicate GenerationRun rows).

### Exit criteria
- Both the dashboard and API reachable on `https://<your-domain>` or `https://<app>.fly.dev`.
- Worker heartbeat ≤ 90 s.
- One full generation→approval→publish cycle completed on production hosting.
- Cloudflared tunnel turned off.

### Kill criterion
If Fly.io billing is still gated → fall back to Option C (home machine, cloudflared, accept ~1 incident per quarter from network).

---

## Risk register (real risks, ranked)

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Operator habit doesn't form (you stop using it) | high | high | Phase 9's 7-day observation is specifically for this; if you don't open `/editor` daily, the product fails regardless of code quality |
| Kimi instability under load | medium | high | Phase 6 fallback to Anthropic Sonnet 4.6 |
| Telethon rate-limit / ban | medium | medium | Phase 7 low poll rate + small channel count; AST guards on write API |
| Editorial quality plateau at `revise` for every generation | medium | medium | Phase 6.1 prompt re-engineering branch |
| Costs creep | low | low | Phase 12 cost dashboard + alarms |
| Telegram changes API or terms | low | high | Bot API only; Telethon read-only on public channels; monitor `python-telegram-bot` releases |
| Hosting downtime | low (Option C) / medium (Options A/B) | medium | Phase 13 decision |

---

## What only the operator can do — a single ranked checklist

When you have an evening / morning to push this forward, this is the order:

1. **(20 min) Phase 6 unblock:** create an Anthropic API key at console.anthropic.com, POST it to `/secrets/anthropic/api_key`. Reply "key in vault". I run the 8-cluster batch.
2. **(15 min) Phase 7 part 1 unblock:** create a Reddit app at reddit.com/prefs/apps (script type, no redirect URL needed), POST client_id + client_secret to `/secrets/reddit/*`. Reply "reddit creds in vault". I wire 5 subreddits.
3. **(45 min) Phase 7 part 2 unblock:** apply for Telethon API access at my.telegram.org (instant), POST API_ID + API_HASH to `/secrets/telethon/*`, then `python -m scripts.create_telethon_session` and type the SMS code locally. Reply "telethon ready". I wire 5 channels.
4. **(30 min) Phase 8 unblock:** create test channel `@chief_editor_test_*`, create bot via @BotFather, add bot as admin, POST bot token + channel id. Reply "test channel ready". I walk you through the gate ritual.
5. **(15 min × 7 days) Phase 9:** approve one post per day. Run the runbook. Watch what happens.

After step 5, the project is **fully functional** in the sense of CLAUDE.md's product vision.

---

## How Claude executes (this plan, in this session and future ones)

- Each phase Claude takes through to "exit criteria except operator-gates".
- At every operator-gate, Claude pauses, reports DB state + exact request shape, asks for confirmation.
- After every phase, Claude runs `pytest -q && ruff check` and commits.
- Memory persists via this file + `OPERATOR_RUNBOOK.md`; both survive context compaction.
- If a session compacts mid-phase, the next Claude reads this file and resumes from the unchecked exit criterion.
