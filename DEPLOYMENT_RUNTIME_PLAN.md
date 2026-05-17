# DEPLOYMENT_RUNTIME_PLAN.md

Bring up a real backend so the Vercel-hosted frontend can flip from
**Demo fallback** → **Connected to live API**. No architecture changes.
One recommended cloud path: **Fly.io** + managed Postgres + Upstash Redis.

## Current Vercel-only reality

- Frontend: deployed at `https://ai-chief-editor-…firdavs39s-projects.vercel.app`.
- It uses `lib/data.ts` → `safeOr` → `lib/demo-fallback.ts` because
  `process.env.NEXT_PUBLIC_API_URL` is not set, so client/server fetches default
  to `http://localhost:8000` which is unreachable from the Vercel runtime.
- `ApiConnectionBadge` already shows "Demo fallback" honestly.
- All readiness/worker endpoints exist server-side but are unreachable from the
  deployed frontend.

## Required runtime

1. **API (FastAPI)** — single web service on `0.0.0.0:8000` (Fly will route on
   8080→8000). Reads env, calls `init_db()` on startup, exposes routers.
2. **Worker** — single long-running Python process, three asyncio loops,
   heartbeats every loop tick. Already SIGTERM-aware.
3. **Postgres** — Fly's managed Postgres (single shared instance is fine for
   alpha; the cheapest dev plan is enough).
4. **Redis** — Upstash via Fly extension (free tier).
5. **Frontend** — already on Vercel; only needs `NEXT_PUBLIC_API_URL`.

## Files this plan creates / changes

### NEW
- `fly.api.toml` — Fly app config for the API service
- `fly.worker.toml` — Fly app config for the worker service
- `docs/DEPLOY_BACKEND_RUNTIME.md` — the runbook
- `packages/shared/chief_editor/logging_config.py` — small structlog setup

### EDITED
- `packages/shared/chief_editor/settings.py` — `frontend_origin`, `public_api_url`
- `apps/api/app/main.py` — env-driven CORS, structured logging hook
- `apps/worker/worker/main.py` — eager initial heartbeat at startup
- `apps/web/lib/types.ts` — `ApiConnectionState` enum
- `apps/web/lib/data.ts` — synthesize 4-state connection
- `apps/web/components/feature/api-connection-badge.tsx` — show 4 states
- `apps/web/app/(app)/settings/page.tsx` — surface worker/integrations gaps
- `apps/web/app/(app)/layout.tsx` — pass worker status into the badge
- `.env.example` — `FRONTEND_ORIGIN`, `PUBLIC_API_URL`
- `README.md` — link to the runtime deploy doc
- `tests/test_cors.py` — new
- `tests/test_settings.py` — extend with new fields

## Required env vars

| Var | Why | Where it lives |
|---|---|---|
| `DATABASE_URL` | Fly managed Postgres connection string | Fly secret on api + worker |
| `REDIS_URL` | Upstash Redis URL | Fly secret on api + worker (currently optional, future-use) |
| `FRONTEND_ORIGIN` | comma-sep origin list for CORS allowlist | Fly secret on api |
| `PUBLIC_API_URL` | the URL this API is reachable at (informational) | Fly secret on api |
| `LIVE_MODE`/`MOCK_MODE`/`DRY_RUN_PUBLISH`/`PUBLISHING_ENABLED` | safety flags | Fly secrets on api + worker |
| `LLM_PROVIDER`, `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` | LLM | Fly secrets on api + worker (NEVER in code) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_TARGET_CHANNEL_ID` | Telegram | Fly secrets on api + worker |
| `TELETHON_API_ID`/`TELETHON_API_HASH`/`TELETHON_SESSION_NAME` | Telethon | Fly secrets on api + worker |
| `REDDIT_*` | Reddit | Fly secrets |
| `POSTIZ_*` | Postiz | Fly secrets |
| `NEXT_PUBLIC_API_URL` | the API URL the browser hits | Vercel project env |

## Deployment risks

| Risk | Mitigation |
|---|---|
| Vercel browser hits HTTP (not HTTPS) → mixed content | Fly gives `https://*.fly.dev` by default |
| Postgres schema drift between Docker compose and Fly | `SQLModel.metadata.create_all()` runs on startup; tables are idempotent |
| Worker writes secrets to logs | structlog config redacts known secret fields; readiness checks already emit `{present, length}` only |
| Worker process crashes silently | Fly restart policy + Healthcheck via `/health` not directly possible on worker, but heartbeat freshness via `/worker/status` makes staleness observable |
| CORS misconfigured → frontend blocked | `FRONTEND_ORIGIN` env is comma-separated, applied at startup; fallback `*` only when unset (dev) |
| Accidentally publishing real content during deploy | All five mode flags default to **safe** (`MOCK_MODE=true`, `DRY_RUN_PUBLISH=true`, `PUBLISHING_ENABLED=false`) until operator opts in |
| Demo seed running against real DB | `POST /demo/seed` wipes tables. Document NOT to call this in production. We will add a `--protect-prod` guard later if needed; for now, runbook says "do not call this in prod" |

## Security risks

| Risk | Mitigation |
|---|---|
| Secrets in container images | Fly secrets are runtime-only; Dockerfiles never bake env |
| Secrets returned in API responses | `readiness/checks.py::_key_meta()` emits `{present, length}` only — already enforced |
| Secrets in logs | `logging_config.py` registers a redactor that drops keys named `*_token`, `*_key`, `*_secret`, `password` from structured records |
| Open CORS in production | `FRONTEND_ORIGIN` strict list; star only when empty (dev fallback) |
| DB exposed | Fly managed Postgres is private to the Fly network; only the api + worker can reach it |
| Demo endpoint hit by anyone | `/demo/seed` is destructive. Out of scope for this pass; documented as "never call in prod". Later: add `DEMO_ENDPOINT_ENABLED` flag |

## Rollback plan

1. **Worker bad deploy** — `fly deploy --image <previous-image-sha>` on the
   worker app. Heartbeat resumes within one minute.
2. **API bad deploy** — same on the api app. Frontend `ApiConnectionBadge`
   flips back to "Demo fallback" automatically until next good deploy.
3. **DB schema regression** — `create_all` only adds new tables/columns;
   destructive changes are out of scope for alpha. If a regression happens,
   restore Fly Postgres snapshot (Fly takes daily by default).
4. **Vercel frontend points at broken API** — flip `NEXT_PUBLIC_API_URL` to an
   empty string in Vercel and redeploy. UI returns to demo fallback.

## Verification checklist

After deploy, in order:

1. `curl https://<api-host>/health` → `{"ok": true, "service": "ai-chief-editor-os-api"}`
2. `curl https://<api-host>/status` → JSON; `mock_mode`, `live_mode`, `dry_run_publish`, `publishing_enabled` present
3. `curl https://<api-host>/readiness` → full report; `overall_score >= 0`
4. `curl https://<api-host>/worker/status` → `overall in {running, partial}` within 60s of worker boot
5. Vercel → set `NEXT_PUBLIC_API_URL=https://<api-host>` → redeploy
6. Open `/settings` → ApiConnectionBadge says **"API connected"**, readiness checklist populated
7. Approve any candidate → Approval Board card shows **"queued (blocked)"** because `PUBLISHING_ENABLED=false`
8. Click **Dry-run preview** in editor → payload visible, `would_send: false`

If all 8 pass, the backend is live and gated correctly. The product is then a
single env flip away from a real first post (per `docs/FIRST_REAL_POST_RUNBOOK.md`).

## Out of scope this pass

- HTTPS custom domain for the API (Fly's `*.fly.dev` is HTTPS by default; custom domain is a 1-minute follow-up)
- Multi-region (single region is fine for alpha)
- Database backups beyond Fly's defaults
- Worker autoscaling (single instance is correct for the current loops)
- Replacing `MockPublisher` fallback when `LIVE_MODE=true && mock not desired` — we already block with `pending_config` job status
- Removing `/demo/seed` from prod (will add `DEMO_ENDPOINT_ENABLED=true` guard in a future pass)
