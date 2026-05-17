# Live Mode runbook

How to take the product from demo to first real Telegram post — without
losing your safety net.

## 0. Prerequisites

- Backend (API + worker) deployed somewhere reachable (Docker / local /
  Fly.io / Railway). The Vercel-only deployment **cannot** publish anything
  because it has no backend attached.
- Postgres + Redis running (Docker compose ships both).
- One real Telegram channel you own + a bot you can attach to it (for the
  Telegram-first path).
- *Or* a Postiz workspace with connected Threads/Reddit integrations (for the
  cross-platform path).

## 1. Phase A — keep everything locked, validate Demo Mode

Make sure the default safety state is honored:

```env
APP_ENV=dev
MOCK_MODE=true
DEMO_MODE=true
LIVE_MODE=false
DRY_RUN_PUBLISH=true
PUBLISHING_ENABLED=false
```

- Restart API + worker.
- Open Settings → all five mode cards show their defaults.
- Run `make seed` (or `POST /demo/seed`) once.

## 2. Phase B — turn on Live Mode for the UI only

```env
LIVE_MODE=true
MOCK_MODE=false   # adapters now require real creds; missing surfaces as warnings
DRY_RUN_PUBLISH=true
PUBLISHING_ENABLED=false
```

The dashboard is now honest about what's missing:

- Settings shows every adapter as `missing_config` until you set its keys.
- Editor shows "publishing disabled" + "dry-run mode" badges.
- Approval Board surfaces approved jobs as `blocked` (master switch off).

## 3. Phase C — connect integrations one at a time

### LLM (pick one)

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-…
```

or

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-…
```

Then on Settings click **Test** next to the LLM row. The probe sends a single
trivial structured-JSON request and validates the shape. Status moves
`configured → valid`.

### Telegram bot

```env
TELEGRAM_BOT_TOKEN=…              # from @BotFather
TELEGRAM_TARGET_CHANNEL_ID=@my_channel  # or numeric id
```

Click **Test** — backend calls `getMe`. Status → `valid` if Telegram accepts.

### Postiz (for Threads + Reddit)

```env
POSTIZ_BASE_URL=https://postiz.example.com
POSTIZ_API_KEY=…
POSTIZ_THREADS_INTEGRATION_ID=…
POSTIZ_REDDIT_INTEGRATION_ID=…
```

Click **Test** — backend calls a Postiz read endpoint
(`/api/v1/integrations` first, falls back to `/api/integrations`, then
`/api/posts?limit=1`). Status → `valid` if any read endpoint returns 2xx.

### Telethon (Telegram monitoring only — read-only)

```env
TELETHON_API_ID=…       # from https://my.telegram.org/apps
TELETHON_API_HASH=…
TELETHON_SESSION_NAME=chief_editor_session
```

A Telethon session has to be created via interactive CLI. Run:

```bash
python -m chief_editor.collectors.telegram --bootstrap   # see INTEGRATIONS.md
```

Status moves `configured → valid` once the `.session` file exists. The web
test endpoint **never** triggers an interactive login.

### Reddit (optional)

```env
REDDIT_CLIENT_ID=…
REDDIT_CLIENT_SECRET=…
REDDIT_USER_AGENT=my-app/1.0 by your_reddit_handle
```

Click **Test** — backend does `POST /api/v1/access_token` with
`client_credentials`. Status → `valid` on success.

## 4. Phase D — dry-run review

For each integration that landed at `valid`:

1. Open `/editor`, pick a candidate.
2. Click **Dry-run preview**. A side drawer shows:
   - exact body the publisher would send
   - body length vs the platform limit
   - whether `would_send` is true (it should still be false during dry-run)
   - safety flags
3. Toggle the platform tabs (Telegram / Threads / Reddit) to inspect each
   payload.

Approve a candidate. The Approval Board now shows it as **queued (dry-run)**
because `DRY_RUN_PUBLISH=true`. The worker dispatches it as a dry-run — a
`PublishResult` row is created with `external_url=dryrun://…` and the payload
preview is attached, but **nothing leaves the box**.

## 5. Phase E — go live, one approved post at a time

When the dry-run preview reads exactly what you want sent:

```env
DRY_RUN_PUBLISH=false
PUBLISHING_ENABLED=true
```

Restart the worker. The next worker tick picks up the existing approved+queued
job and **now** dispatches it through the real publisher.

Watch:

- `/worker/status` — `publisher_dispatch` event should fire within 30s.
- `/calendar` — the job moves from `pending` → `done`.
- The Telegram channel / Postiz dashboard — confirm the post appeared.

## 6. Phase F — rollback

If anything looks off, flip the master switch back:

```env
PUBLISHING_ENABLED=false
```

Restart worker. New approved jobs become `blocked` again. The already-sent
posts are obviously not undone — that's a deliberate human action via the
relevant platform.
