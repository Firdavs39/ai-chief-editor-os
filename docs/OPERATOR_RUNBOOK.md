# Operator Runbook — AI Chief Editor OS

> The minimal set of actions the operator (you) must perform to take a
> draft from generated → live on a real channel.
>
> **Claude never performs the actions in this runbook.** They are the
> product safety contract.

---

## Daily workflow (Phase 9 onwards)

### Morning, ~10 minutes per post

1. **Open the dashboard** at `http://localhost:3000/dashboard` (or your production URL).
2. **Trend Radar** (`/trends`) — pick a cluster that's worth writing about today.
3. Click **Generate Brief**. Wait ~20–30 minutes. (Worker advances one step per tick.)
4. When the candidate appears in **`/editor`**, read all three platform versions plus the **Critic Report** and **Quality Report** artifacts.
5. Decide:
   - **Reject** — start over with a different cluster.
   - **Rewrite** — click rewrite, pick a tone, regenerate.
   - **Approve** — proceed to "The 4-step publish ritual" below.

---

## The 4-step publish ritual

> **Every step requires you to flip a flag or click a button.** Claude does
> not flip flags. This is the safety contract.
>
> The product is designed so that even if Claude is wrong, malicious, or
> compromised, no publication can happen without your hand on each gate.

### Step 1 — Approve

Click **Approve** on the candidate card in `/editor`.

Verification:
```
GET /candidates/{id} → status: "approved"
GET /publishing/jobs?candidate_id={id} → status: "pending"
```

At this point: **nothing has left the box**. The job is just queued in your local DB.

### Step 2 — Confirm "blocked" state (default safety)

Within ~30 seconds the worker ticks. Verify:
```
GET /publishing/jobs?candidate_id={id} → status: "blocked"
```

This proves that with both flags off (`PUBLISHING_ENABLED=false`, `DRY_RUN_PUBLISH=true`), the worker refuses to dispatch even an approved job. ✓

### Step 3 — Dry-run rehearsal

You flip ONE flag:
```
PUBLISHING_ENABLED=true
DRY_RUN_PUBLISH=true   (unchanged)
```

Where: edit `.env` and restart the worker. Or via `/settings` (when the UI lands in Phase 8).

Within ~30 seconds, verify:
```
GET /publishing/jobs?candidate_id={id} → status: "dry_run"
```

Inspect what would have been sent:
```
GET /publishing/results?job_id={...} → payload preview
```

This proves the publisher built a real payload but **did not contact any external service**. ✓

### Step 4 — Real publish

You flip the second flag:
```
PUBLISHING_ENABLED=true
DRY_RUN_PUBLISH=false
```

Within ~30 seconds:
```
GET /publishing/jobs?candidate_id={id} → status: "running" → "done"
```

Open Telegram. Verify the message is in the target channel.

### Step 5 — Revert flags (MANDATORY)

Set both back to safe defaults:
```
PUBLISHING_ENABLED=false
DRY_RUN_PUBLISH=true
```

Restart the worker.

**Why mandatory:** the open state is what makes a future bug catastrophic. The closed state is what makes the product safe between publishes.

---

## Vault setup — one-time, per integration

Every credential the product needs lives in the Integration Secrets Vault, encrypted with Fernet at rest. You never paste a credential into chat. Claude never sees the plaintext.

### Required environment (already in `.env`)
```
MASTER_ENCRYPTION_KEY=<Fernet key>
ADMIN_TOKEN=<random 32+ chars>
```

If these are missing, the Vault refuses writes with HTTP 409.

### Per-integration setup

For each integration below, the form is:
```
curl -X POST http://localhost:8000/secrets/{provider}/{key_name} \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value":"<the-actual-secret>"}'
```

Or via the `/settings/integrations` UI (Phase 8).

### 1. Anthropic (Phase 6 fallback)
- Create key at https://console.anthropic.com → API Keys.
- POST to `/secrets/anthropic/api_key`.
- Verify: `POST /readiness/test-llm` returns `{ok: true, provider: "anthropic"}`.

### 2. Reddit (Phase 7)
- Create app at https://www.reddit.com/prefs/apps → "script" type, no redirect.
- POST `client_id` to `/secrets/reddit/client_id`.
- POST `client_secret` to `/secrets/reddit/client_secret`.
- Verify: `POST /readiness/test-reddit` returns OAuth-grant success.

### 3. Telethon (Phase 7)
- Apply at https://my.telegram.org → API Development Tools → create app.
- POST `api_id` to `/secrets/telethon/api_id`.
- POST `api_hash` to `/secrets/telethon/api_hash`.
- **Generate the session file ON YOUR MACHINE**:
  ```
  python -m scripts.create_telethon_session
  ```
  This will prompt for your phone number, send you an SMS code (which you type locally), and write the session to `data/telethon/chief_editor.session`. **Claude must not see the code.**
- Verify: `POST /readiness/test-telethon` returns presence + session-file OK.

### 4. Telegram Bot (Phase 8)
- Open Telegram → talk to `@BotFather` → `/newbot` → follow prompts → get token.
- Add the bot to your test channel as **admin** (channel settings → administrators).
- Get the channel id: send any message to `@RawDataBot` from the channel, copy the `id` field (negative number for channels).
- POST `bot_token` to `/secrets/telegram/bot_token`.
- POST `target_channel_id` to `/secrets/telegram/target_channel_id`.
- Verify: `POST /readiness/test-telegram-bot` returns `getMe` success + (optional) `getChat` for the target channel.

### 5. Postiz (post-Phase-9, multi-platform)
- Create Postiz account at https://postiz.com → API → key.
- POST `base_url` to `/secrets/postiz/base_url`.
- POST `api_key` to `/secrets/postiz/api_key`.
- POST integration IDs to `/secrets/postiz/threads_integration_id`, `/secrets/postiz/reddit_integration_id`.

---

## What to do when something goes wrong

### "Worker hasn't ticked in N minutes"
1. Check the worker process is alive: `Get-Process python | Format-Table Id, CommandLine`.
2. Check the worker log: `Get-Content .phase52_worker.log -Tail 50`.
3. If hung: restart it: `Stop-Process -Id <pid>; python -m worker.main > .worker.log 2>&1 &`.

### "A run failed at step N"
1. Check the run's error in `/editor/runs/{run_id}`.
2. If the error is `ValidationError` with `string_too_long` → schema legitimately rejected over-long output; the model needs prompt tuning OR the schema for THAT field needs raising. Don't silently clamp.
3. If `ValidationError` with other types → check whether the validation-aware repair fired (grep worker log for `repair_attempted`).
4. If `OllamaProvider` raised → Ollama Cloud is down or rate-limited. Wait 5 min and retry.

### "An approved job stays in `pending` forever"
The worker is not ticking. See above.

### "A job moved to `blocked` even though I set `PUBLISHING_ENABLED=true`"
1. Restart the worker — env vars are read at startup, not per-tick.
2. Verify the value the worker sees: `GET /status` returns `publishing_enabled: true`.

### "A real message was published WITHOUT me flipping flags"
**STOP. Halt everything.** This is a safety-contract violation. Disable publishing immediately:
```
PUBLISHING_ENABLED=false
DRY_RUN_PUBLISH=true
```
Restart the worker. File an incident in `publish_incidents` table. Open the bug.

---

## Quick reference card (print this)

```
                       PUBLISHING_ENABLED    DRY_RUN_PUBLISH    Result
                       ──────────────────    ───────────────    ──────
default (always safe): false                 true               blocked
rehearsal:             true                  true               dry_run (preview only)
LIVE PUBLISH:          true                  false              real send
the dangerous state:   true                  false              ← always revert after publish

approval gate:         decision='approve' required in EVERY case
publisher gate:        Telegram/Postiz creds must be present for non-mock
```

**Three independent gates. All three must be green for one send. After every send: revert.**
