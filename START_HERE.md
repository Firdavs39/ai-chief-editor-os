# START HERE — AI Chief Editor OS

> If you just pulled this branch and want to actually USE the system,
> read this single page. Other docs are deep-dives; this is the
> 5-minute "do this in this order" guide.

---

## What this system does

**One sentence:** every morning, AI Chief Editor OS reads ~10 sources you
care about, finds the top-scoring trend, generates a draft post in your
voice for Telegram + Threads + Reddit, runs a deterministic AI-tells
detector on it, then waits for you to approve / reject / rewrite.

**One screen:** `http://localhost:3000/dashboard`. Open it. The rest of
this doc tells you what to click.

---

## Step 0 — Verify the stack is up (≤30 sec)

**One command does it all:**

```bash
PYTHONPATH="packages/shared;apps/api;apps/worker" python -m scripts.smoke_test
```

29 checks across API / dashboard / data / detector / Vault. If you
see `Smoke test: 29 passed, 0 failed, 0 warned -> ALL GREEN`, you're
good. Skip to Step 1.

If any check FAILS, start the missing process:

```bash
# API
PYTHONPATH="packages/shared;apps/api;apps/worker" python -m uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000

# Worker
PYTHONPATH="packages/shared;apps/api;apps/worker" python -m worker.main

# Frontend
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8000 pnpm dev
```

Then re-run the smoke test. All-green is the precondition for daily
editorial work.

---

## Step 1 — Open the dashboard, see real trends (1 min)

Open `http://localhost:3000/trends`.

You should see ~50 trend clusters. Most are real (pulled from 11 RSS
sources — vc.ru, Habr, TechCrunch, MIT Tech Review, Anthropic news,
Hacker News, etc.). A handful are demo seed (from `make seed`).

Each cluster has:
- A topic line (representative_text)
- A score (total_score) with breakdown by component
- Source signals it was clustered from
- Language tag (ru / en)

Sort by total_score descending — that's the default. Top one is what
the system thinks is hottest right now.

---

## Step 2 — Generate a brief on a real cluster (~30-45 min Kimi time)

1. Click a cluster you'd actually want to write about.
2. Click **"Generate Quality Brief"** in the cluster card. (Or use the
   API: `POST /generation-runs` with `cluster_id`.)
3. You'll be returned to `/editor` with a new candidate marked
   "generating".
4. **Wait ~30-45 minutes.** Kimi runs an 11-step workflow:
   research → angle → audience-psychology → style-DNA → 3 platform
   writers → critic (with deterministic flag merge) → editor-in-chief →
   quality-judge → finalizer.

You can close the tab and come back. The worker keeps running. When
you return, the candidate will be `status="draft"`.

**Don't expect "viral" output every time.** The system produces
publishable drafts ~80% of the time given a usable cluster. The rest
need rewriting or rejection. That's the editorial loop.

---

## Step 3 — Read the candidate critically (5-10 min)

Open `/editor/{candidate_id}`. You'll see:

- **3 platform versions** — Telegram (target 800-1500 chars), Threads
  (180-380), Reddit (60-90 char title + 800-2000 body).
- **Critic Report** — `slop_count`, `factual_concerns`, `length_issues`,
  `hook_grade` (0-10). The `length_issues` field includes
  **deterministic flags** the Python detector caught (em-dash density,
  banned-phrase hits, missing anchors, etc.).
- **Quality Judge** — `style_match_score`, `viral_score`, `slop_risk`,
  `controversy_risk` (0-1 each) + `recommendation` (approve / revise /
  reject).

**Read in this order:**
1. The hook (first 80 chars of Telegram body). Does it stop your scroll?
2. The critic flags. Does it call out anything you also notice?
3. The judge scores. Specifically `slop_risk` — anything above 0.30 is
   AI-flavored.
4. The full TG body. Would YOU post this with your name on it?

If yes → approve. If no → reject (the cluster might not be a good
topic) or rewrite (`POST /candidates/{id}/rewrite` with mode `sharper`
/ `expert` / `shorter` / `human` / `deslop`).

---

## Step 4 — Stop here for the first day

Do not yet:
- Configure Telegram bot credentials
- Flip `PUBLISHING_ENABLED=true`
- Try to actually publish

The first day's goal is **reading drafts**. See if the output is
useful. If it's not, all the publishing config is wasted effort.

If after generating 2-3 candidates the quality feels right, proceed
to Step 5. If not, file an issue describing what's missing — the
prompts can be tuned without a re-architecture.

---

## Step 5 — When you're ready to actually publish

Read these in order:

1. **[`docs/OPERATOR_RUNBOOK.md`](docs/OPERATOR_RUNBOOK.md)** — the
   4-step publish ritual. Lists every credential you need to provide
   (Telegram bot token, target channel id) and the EXACT order to flip
   the two safety flags.

2. **[`docs/HANDOFF.md`](docs/HANDOFF.md)** — section 2 "What's left
   for the operator". Ordered checklist with time estimates per step
   (Phase 7 Reddit creds, Phase 7 Telethon session, Phase 8 safety
   rehearsal, Phase 9 daily publish).

3. **[`docs/PHASE_PLAN.md`](docs/PHASE_PLAN.md)** — full roadmap. Each
   phase has exit + kill criteria. Use this to know when a phase is
   "done" vs "needs more work".

---

## Step 6 — When you want to publish to a TEST channel first

This is Phase 8. Don't skip it. Even after you've configured
everything, the system has THREE safety gates between draft and live
post. The safety walker proves all three work:

```bash
PYTHONPATH="packages/shared;apps/api;apps/worker" \
  python -m scripts.phase8_safety_walker \
  --candidate-id <your-approved-candidate-id> \
  --admin-token <ADMIN_TOKEN from .env>
```

The script walks you through:
1. Approve → DB shows `PublishJob(status=pending)`
2. Worker tick with both flags off → `status=blocked` ✓
3. You flip `PUBLISHING_ENABLED=true`, keep `DRY_RUN_PUBLISH=true` →
   `status=dry_run` (payload computed, nothing sent)
4. You flip `DRY_RUN_PUBLISH=false` → `status=running → done`
5. Real Telegram message in test channel
6. **You revert both flags** to safe defaults

**Claude never flips flags. The safety contract.**

---

## Common questions

**"How much does this cost to run?"** Real Kimi (Ollama Cloud) charges
~$0.10-0.15 per full 11-step workflow run. If you publish 1 post per
day, ~$3-5/month total.

**"Can I use Anthropic Claude instead?"** Yes, but not by default —
the system is configured Kimi-only per operator decision. To switch:
provide `ANTHROPIC_API_KEY` via `/secrets/anthropic/api_key`, change
`LLM_PROVIDER=anthropic` in `.env`, restart worker. All Phase Q work
works with either model.

**"Why is one run taking forever?"** Most likely Ollama Cloud is
slow. The new prompts (Phase Q v4 trim) typically produce step durations
of 60-120s on Kimi. If a step is running >15 min, check
`worker_qv7_final.log` for errors. The detector and validation-aware
repair (Phase 5.2) handles most error classes automatically.

**"How do I know if a draft is 'good enough' to publish?"** Heuristic
floor: `slop_risk ≤ 0.30` AND `viral_score ≥ 0.70` AND `controversy_risk ≤ 0.60`
AND the critic_report has ≤2 length_issues. Beyond that — your call as
the editor.

**"Can I trust this won't accidentally publish?"** Yes — three independent
gates (API approval check + worker gate + publisher gate), each tested
in `tests/test_publishing_safety*.py`. They all default to safe. You'd
have to actively flip 2 environment variables AND make a draft AND
approve it to send anything.

---

## What's in this PR that wasn't in main

See [`docs/CHANGELOG_PHASE_5_2_TO_Q.md`](docs/CHANGELOG_PHASE_5_2_TO_Q.md)
for the full diff narrative. Highlights:

- **Phase 5.2** — schema fix for Kimi length-overflow (the original Phase
  5.1 failure mode is now solved).
- **Phase 7** — 11 real RSS sources wired and producing real trends.
- **Phase Q** — research-grounded prompt rewrite + deterministic
  AI-tells detector + Sierra-style critic supervisor + Bad/Good
  anti-example pairs. Output quality visibly sharper.
- **TD-1 fix** — legacy generation_loop no longer competes with Phase
  5.2+ workflow runs for the worker thread.

**+5500 lines / 32 files / 366 tests passing / ruff clean / 0 safety
regressions.**

---

If you read nothing else, read steps 1-3 above. The product is in your
dashboard, right now, at `http://localhost:3000/dashboard`.
