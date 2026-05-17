# First real post — runbook

This is the **shortest** path to your first real Telegram post that the
product can take. Read `SAFETY_MODEL.md` first.

## Telegram (Bot API) — first real post

### Prereqs

- Backend (API + worker) running locally or on Fly/Railway, **not** Vercel
  alone (Vercel hosts only the Next.js dashboard).
- Postgres + Redis up.
- A bot token from @BotFather.
- A channel where you're admin, plus the bot added as admin.

### Steps

1. **Demo-validate the path.**
   ```env
   MOCK_MODE=true
   LIVE_MODE=false
   DRY_RUN_PUBLISH=true
   PUBLISHING_ENABLED=false
   ```
   Restart. Approve any seeded candidate. Worker logs a `dry_run` dispatch.
   You see `Approval Board → Approved & scheduled → queued (dry-run)`.

2. **Switch to honest Live UX.**
   ```env
   LIVE_MODE=true
   MOCK_MODE=false
   ```
   Restart. Settings shows everything as `missing_config`.

3. **Fill Telegram bot creds only.**
   ```env
   TELEGRAM_BOT_TOKEN=…
   TELEGRAM_TARGET_CHANNEL_ID=@your_channel
   ```
   Click **Test** in Settings → row turns `valid` with the bot username.

4. **Fill LLM creds (or stay on mock).**
   ```env
   LLM_PROVIDER=anthropic
   ANTHROPIC_API_KEY=sk-ant-…
   ```
   Click **Test** → `valid`.

5. **Dry-run preview the post.**
   - Generate a candidate (`POST /brief/generate` or `/editor`).
   - Click **Dry-run preview** in the editor — confirm the exact body that
     would be sent. Check `would_send` reads `false` because dry-run is on.

6. **Approve.**
   - Approval Board now shows the job as **queued (dry-run)**.
   - Worker tick records a `dry_run` PublishResult with the payload preview.

7. **Lift the dry-run guard.**
   ```env
   DRY_RUN_PUBLISH=false
   ```
   Restart worker only (API doesn't need a restart).

   The approved+queued job is still `pending` (or already `dry_run` from the
   previous tick — reopen the candidate and re-approve to create a fresh job
   if you want it dispatched now).

8. **Flip the master switch.**
   ```env
   PUBLISHING_ENABLED=true
   ```
   Restart worker.

9. **Watch.**
   - `/worker/status` — `publisher_dispatch` event timestamp updates.
   - Approval Board — the card moves to **Published** column.
   - Your Telegram channel — the post is live.

10. **(Optional) Lock back down.**
    ```env
    PUBLISHING_ENABLED=false
    ```
    Restart worker. The system returns to "approve → blocked" until you
    deliberately flip the switch again.

## Threads / Reddit via Postiz — first real post

Same shape, with Postiz in place of `TELEGRAM_*`:

1. Configure `POSTIZ_BASE_URL`, `POSTIZ_API_KEY`, `POSTIZ_THREADS_INTEGRATION_ID`.
2. Click **Test** Postiz → status `valid`.
3. In editor, dry-run preview for `threads` platform → review payload.
4. Approve. Worker dispatches dry-run first.
5. Flip `DRY_RUN_PUBLISH=false` + `PUBLISHING_ENABLED=true`.
6. Approve again → real post via Postiz.

## What to expect if a step fails

| Symptom | Likely cause | Where to look |
|---|---|---|
| Test button returns `error` | Network or auth error | The `safe_details` block on that readiness row |
| Test returns `invalid` | Telegram rejected token (401), Reddit rejected client creds, Postiz returned 4xx | Same |
| Approval succeeds but no publish | Master switch off, dry-run on, or publisher missing creds in Live Mode | Approval Board card hint + `SystemLog` rows like `publisher.dispatch.blocked` |
| Worker status `stale` | Worker process died or wasn't started | `docker compose ps worker` / `python -m worker.main` logs |
