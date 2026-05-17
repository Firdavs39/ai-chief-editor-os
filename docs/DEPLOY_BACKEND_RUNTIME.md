# Deploy backend runtime — Fly.io

The simplest practical path for a single founder. One target cloud,
two Fly apps, managed Postgres, Upstash Redis. ~15 minutes end-to-end.

> Why Fly.io: same Dockerfiles you already use, free hobby plan covers
> alpha, managed Postgres and Upstash Redis are one command each,
> long-running worker process is a first-class concept.

If you prefer Railway / Render / Hetzner, the env-var contract below is
identical — only the `fly` commands change.

## Pre-flight

You need:

- A Fly.io account (`fly.io/signup`).
- The `flyctl` CLI: `brew install flyctl` / `iwr https://fly.io/install.ps1 -useb | iex`
  / `curl -L https://fly.io/install.sh | sh`.
- This repo cloned locally.
- Existing Vercel frontend deployed (it is — see the previous deploy doc).

Login once:

```bash
fly auth login
```

## 1. Create Postgres

```bash
fly postgres create --name chief-editor-db --region fra --vm-size shared-cpu-1x --initial-cluster-size 1
```

Fly prints a `DATABASE_URL`. Save it locally — you'll attach it as a secret.
It looks like `postgres://postgres:<password>@chief-editor-db.flycast:5432`.

Convert the scheme to SQLModel/psycopg form when you set the env var
(append the driver hint):

```
postgresql+psycopg://<user>:<password>@chief-editor-db.flycast:5432/postgres
```

## 2. Create Redis (Upstash via Fly)

```bash
fly redis create --name chief-editor-redis
```

Pick the free tier. Save the printed `REDIS_URL` (starts with
`redis://default:<password>@...upstash.io:6379`).

> Redis is not strictly required for the alpha — the app falls back to
> SQLite + SQLModel when neither is set. But it is set up here so the
> worker and API share a cache surface for any future use.

## 3. Launch the API app

```bash
fly launch --copy-config --no-deploy --config fly.api.toml --name chief-editor-api
```

Decline Fly's auto-Postgres prompt — you already created it.

Attach the DB so Fly puts it on the same private network:

```bash
fly postgres attach --app chief-editor-api chief-editor-db
```

Set the rest of the secrets (paste real values — never commit):

```bash
fly secrets set --app chief-editor-api \
  DATABASE_URL='postgresql+psycopg://postgres:<password>@chief-editor-db.flycast:5432/postgres' \
  REDIS_URL='redis://default:<password>@<host>.upstash.io:6379' \
  FRONTEND_ORIGIN='https://ai-chief-editor-os.vercel.app,https://<your-custom-domain>' \
  PUBLIC_API_URL='https://chief-editor-api.fly.dev' \
  LIVE_MODE=true \
  MOCK_MODE=true \
  DEMO_MODE=false \
  DRY_RUN_PUBLISH=true \
  PUBLISHING_ENABLED=false
```

> Leave `MOCK_MODE=true` for the first deploy. You can flip it to `false`
> AFTER you've added at least one set of integration credentials.

Deploy:

```bash
fly deploy --config fly.api.toml
```

Watch the build. The `release_command` runs `init_db()` to create tables.

Verify:

```bash
curl https://chief-editor-api.fly.dev/health
curl https://chief-editor-api.fly.dev/status
curl https://chief-editor-api.fly.dev/readiness | head -c 400
```

You should see `mock_mode=true`, `live_mode=true`, `dry_run_publish=true`,
`publishing_enabled=false` in `/status`. The readiness report should list
all sections with mostly `missing_config` items.

## 4. Launch the worker app

```bash
fly launch --copy-config --no-deploy --config fly.worker.toml --name chief-editor-worker
fly postgres attach --app chief-editor-worker chief-editor-db
```

Set the **same** secrets as the API (DB, Redis, mode flags, any
integration credentials). Fastest way:

```bash
fly secrets set --app chief-editor-worker \
  DATABASE_URL='postgresql+psycopg://postgres:<password>@chief-editor-db.flycast:5432/postgres' \
  REDIS_URL='redis://default:<password>@<host>.upstash.io:6379' \
  LIVE_MODE=true \
  MOCK_MODE=true \
  DEMO_MODE=false \
  DRY_RUN_PUBLISH=true \
  PUBLISHING_ENABLED=false
```

Deploy:

```bash
fly deploy --config fly.worker.toml
```

Within ~30 seconds, the worker writes its first heartbeats. Verify from
the API:

```bash
curl https://chief-editor-api.fly.dev/worker/status
```

Look for `"overall": "running"` and three loops (`collector`,
`generation`, `publisher`) with `"fresh": true`.

## 5. Seed (optional, for demo flow against real DB)

The product runs without seeding, but if you want the dashboard to look
"alive" against the live DB:

```bash
curl -X POST https://chief-editor-api.fly.dev/demo/seed
```

> The demo seed **wipes** the relevant tables before inserting. Don't call
> this against a DB with real approvals.

## 6. Point Vercel at the live API

In the Vercel dashboard (or via CLI):

```bash
cd apps/web
vercel env add NEXT_PUBLIC_API_URL production
# paste: https://chief-editor-api.fly.dev
vercel --prod --yes
```

Or via the dashboard: Project → Settings → Environment Variables →
`NEXT_PUBLIC_API_URL` = `https://chief-editor-api.fly.dev` for production.
Redeploy from "Deployments" tab.

## 7. Confirm the flip

Open the production URL of the Vercel project. In the bottom-left corner
the `ApiConnectionBadge` should now read **"API connected"** (green) instead
of the previous **"Demo fallback"**.

Open `/settings`:

- "API connection" card shows your Fly URL as `Connected`.
- "Readiness checklist" populates from the live API.
- "First real post" checklist shows real state.
- "Worker process" row shows `fresh` heartbeats.

## 8. Rollback

If anything looks off:

| Symptom | Fix |
|---|---|
| API responding 5xx | `fly releases --app chief-editor-api` → `fly deploy --image <previous-image-tag>` |
| Worker dead | `fly status --app chief-editor-worker` → `fly machine start --app chief-editor-worker` |
| Frontend shows "Demo fallback" but API is healthy | Check `NEXT_PUBLIC_API_URL` in Vercel; missing trailing slash is fine, extra one breaks |
| Worker heartbeat stale | `fly logs --app chief-editor-worker` for crash trace; if `DATABASE_URL` wrong, the worker still boots but can't write heartbeats |
| Approve doesn't dispatch | Expected — `PUBLISHING_ENABLED=false` blocks at the master gate. See `docs/FIRST_REAL_POST_RUNBOOK.md` |

To revert the Vercel frontend to demo fallback:

```bash
vercel env rm NEXT_PUBLIC_API_URL production
vercel --prod --yes
```

## 9. Costs

Single-founder alpha on Fly.io free tier:
- 1 shared-cpu-1x / 512MB VM for API: **~$0** (within free tier)
- 1 shared-cpu-1x / 512MB VM for worker: **~$0** (within free tier)
- Postgres `shared-cpu-1x`: **~$2/mo** (smallest paid tier; the free shared one is going away)
- Upstash Redis free tier: **$0** for 10k commands/day
- Vercel hobby: **$0**

Total: **~$2–5/month** for the alpha.

## 10. First live dry-run (right after backend is up)

This is the audit you should do **immediately after** the badge says
"API connected", before considering any real publish.

| # | Action | Expected |
|---|---|---|
| 1 | `curl https://chief-editor-api.fly.dev/health` | `{"ok":true,"service":"ai-chief-editor-os-api"}` |
| 2 | `curl https://chief-editor-api.fly.dev/status` | `mock_mode:true, live_mode:true, dry_run_publish:true, publishing_enabled:false` |
| 3 | `curl https://chief-editor-api.fly.dev/readiness | jq '.overall_score'` | numeric, ≥ 30 if at least mode + worker are valid |
| 4 | `curl https://chief-editor-api.fly.dev/worker/status | jq '.overall'` | `"running"` |
| 5 | `curl -X POST https://chief-editor-api.fly.dev/demo/seed` | summary with 6 sources / 10 clusters / 8 candidates |
| 6 | Pick a candidate id from `/candidates`, then `curl -X POST .../readiness/dry-run-publish/<id>?platform=telegram` | `preview.dry_run=true`, `preview.would_send=false` |
| 7 | In UI, approve the candidate | Approval Board card shows **"queued (blocked)"** because `PUBLISHING_ENABLED=false` |
| 8 | Wait 30 seconds. `curl .../publishing/jobs` | The job for that candidate has `status: "blocked"` |
| 9 | `fly logs --app chief-editor-worker | grep publisher.dispatch.blocked` | At least one entry — confirms the worker saw the approved job AND refused to dispatch it |

If all 9 pass, you have a **demonstrably safe** live backend.

To proceed to a real first post follow `docs/FIRST_REAL_POST_RUNBOOK.md`.
The path is intentionally narrow:

```
add real integration creds (1 secret at a time) → /readiness/test-* → green
DRY_RUN_PUBLISH=false   ← worker restarts, approved jobs become "queued" not "dry_run"
PUBLISHING_ENABLED=true ← master gate opens
re-approve a candidate → worker dispatches via real publisher.
```

Any one of those three flags being off keeps a real post impossible.

## 11. What is NOT done by this runbook

- Custom domain (`fly certs add api.your-domain.com` is a one-liner; out of scope here).
- Multi-region (single region is fine).
- DB backups beyond Fly's daily snapshots.
- Telethon session file — must be created locally via the bootstrap script
  in `docs/INTEGRATIONS.md` and uploaded via `fly ssh sftp put` if needed.
- Threads/Telegram real publishing — gated behind `PUBLISHING_ENABLED=true`
  per `docs/FIRST_REAL_POST_RUNBOOK.md`.
