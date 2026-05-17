# LIVE_MODE_READINESS_PLAN.md

Internal implementation plan for the Live Mode Readiness layer.
This is **not** a rebuild. It is a thin safety + readiness layer on top of the
existing app. Approval gate, demo mode, mock fallbacks remain intact.

## Current architecture (summary)

```
apps/web              Next.js 15 dashboard (already polished, deployed on Vercel)
apps/api              FastAPI; routers: health, status, sources, trends, collect,
                      briefs, candidates, approvals, publishing, calendar,
                      analytics, style_profile, demo
apps/worker           async worker — collector_loop, generation_loop, publisher_loop
packages/shared
  └─ chief_editor
      ├─ settings.py         (pydantic-settings)
      ├─ models/             (SQLModel: 11 tables)
      ├─ services/{approval, candidate, pipeline, …}
      ├─ llm/{base, mock, anthropic, openai, registry}
      ├─ publishing/{base, mock, telegram, postiz, registry}
      └─ collectors/{base, mock, telegram, reddit, rss, registry}
```

Approval invariants today:
1. `Publisher.publish()` raises `ApprovalRequiredError` if `approval.decision != "approve"`.
2. API route `POST /publishing/jobs` refuses if no approve decision exists.
3. Worker `_dispatch_one()` re-validates approval before calling publisher.

What's missing for Live Mode:
- Master kill-switch (`PUBLISHING_ENABLED`).
- Universal dry-run mode (`DRY_RUN_PUBLISH`).
- Honest readiness reporting (LLM, TG bot, Telethon, Reddit, Postiz, worker).
- Worker heartbeat.
- UI surface for first-real-post safety walkthrough.

## Files that will change

### Shared core
- `packages/shared/chief_editor/settings.py` — new flags `demo_mode`, `live_mode`, `dry_run_publish`, `publishing_enabled`, `worker_heartbeat_ttl_seconds`
- `packages/shared/chief_editor/readiness/__init__.py` — **new**
- `packages/shared/chief_editor/readiness/models.py` — **new** (enums + pydantic types)
- `packages/shared/chief_editor/readiness/checks.py` — **new** (per-integration safe checks)
- `packages/shared/chief_editor/readiness/worker.py` — **new** (heartbeat read)
- `packages/shared/chief_editor/models/heartbeat.py` — **new** (`WorkerHeartbeat`)
- `packages/shared/chief_editor/models/__init__.py` — register heartbeat
- `packages/shared/chief_editor/services/approval.py` — gate-aware initial job status
- `packages/shared/chief_editor/services/dry_run.py` — **new** (payload preview)

### API
- `apps/api/app/routers/readiness.py` — **new**
- `apps/api/app/routers/worker.py` — **new** (`GET /worker/status`)
- `apps/api/app/main.py` — register two new routers
- `apps/api/app/routers/status.py` — extend with new mode flags

### Worker
- `apps/worker/worker/main.py` — write `WorkerHeartbeat` per loop, gate `_dispatch_one` on PUBLISHING_ENABLED / DRY_RUN_PUBLISH

### Frontend
- `apps/web/lib/types.ts` — add `Readiness*`, `WorkerStatus`, extend `StatusPayload`
- `apps/web/lib/api.ts` — add readiness/worker endpoints + connection probe
- `apps/web/lib/data.ts` — track API reachability flag (for Vercel honesty)
- `apps/web/components/feature/readiness-section.tsx` — **new**
- `apps/web/components/feature/test-button.tsx` — **new**
- `apps/web/components/feature/api-connection-badge.tsx` — **new**
- `apps/web/components/feature/first-post-checklist.tsx` — **new**
- `apps/web/app/(app)/settings/page.tsx` — overhaul into Live Mode Control Center
- `apps/web/app/(app)/editor/[id]/page.tsx` — platform-readiness badges + dry-run preview button
- `apps/web/app/(app)/approvals/page.tsx` — show `blocked` / `pending_config` / `dry_run` distinctly
- `apps/web/app/(app)/layout.tsx` — show API connection badge

### Env / config
- `.env.example` — add five new vars

### Docs
- `docs/LIVE_MODE_RUNBOOK.md` — **new**
- `docs/FIRST_REAL_POST_RUNBOOK.md` — **new**
- `docs/INTEGRATIONS.md` — **new**
- `docs/SAFETY_MODEL.md` — **new**
- `README.md` — append "Live Mode" section + Vercel/local/Docker matrix

### Tests
- `tests/test_readiness.py` — **new**
- `tests/test_publishing_safety.py` — **new**
- `tests/test_worker_status.py` — **new** (light, no event loop)
- existing tests must keep passing

## Risks

| Risk | Mitigation |
|---|---|
| Breaking existing 36 tests | New gates only fire in worker `_dispatch_one`, not in `MockPublisher.publish()`. Defaults keep tests in pre-Live behavior |
| Exposing secrets via test endpoint reflection | All readiness items carry only `safe_details` and `missing_env_vars` (names only) |
| Network hang during test endpoints | All real HTTP probes use `httpx` with 5s timeout, exception → `error` status |
| Telethon test triggering interactive login | Never instantiate `TelegramClient`. Only check `has_telethon` + session file presence |
| Postiz test creating real post | Only call read-style endpoint (`GET /integrations` or list posts) — never POST |
| Worker heartbeat row contention | Single upsert per loop, indexed by `loop_name` |
| Schema migration in production | SQLModel `create_all` is idempotent — new table appears, existing tables untouched |

## Safety invariants (re-asserted)

| Invariant | Where enforced |
|---|---|
| Approval required | `Publisher.publish()` + `_dispatch_one()` + `POST /publishing/jobs` |
| `PUBLISHING_ENABLED=false` blocks all real publish | NEW in `_dispatch_one()` |
| `DRY_RUN_PUBLISH=true` blocks all real publish | NEW in `_dispatch_one()` |
| No secrets returned to FE | Readiness checks only emit boolean presence + length |
| No real publish from test endpoints | All test endpoints are explicitly read-only / identity-only |
| RSS works without creds | `RssCollector` already feedparser-only |
| Threads via Postiz only | `PostizPublisher` is the only Threads route |
| Reddit via official API | `RedditCollector` uses asyncpraw |
| Telegram monitor = Telethon, publish = Bot API | unchanged |

## Backend endpoint plan

| Method | Path | Purpose |
|---|---|---|
| GET | `/readiness` | full report: mode + all integration sections + overall score |
| POST | `/readiness/test-llm` | live ping LLM if configured; safe schema completion |
| POST | `/readiness/test-telegram-bot` | call `getMe`; optionally `getChat` for target |
| POST | `/readiness/test-telethon` | check creds + session file existence; never log in |
| POST | `/readiness/test-reddit` | OAuth handshake via asyncpraw read-only |
| POST | `/readiness/test-postiz` | call Postiz read endpoint (list integrations) |
| POST | `/readiness/test-source/{id}` | per-source: RSS parse-once, TG/Reddit cred check |
| POST | `/readiness/dry-run-publish/{candidate_id}` | compute exact payload, never send |
| GET | `/worker/status` | heartbeat freshness per loop + last event timestamps |

All return HTTP 200 with structured `ReadinessItem` even when "broken" — never 5xx for missing config.

## Frontend UI plan

- **Settings = Live Mode Control Center**
  - Mode Overview row (5 mode cards)
  - Readiness Checklist (sections: LLM, Telegram, Telethon, Reddit, Postiz, Worker, Sources, Publishing Safety) — each item has a Test button when applicable
  - First Real Post Checklist (computed from current readiness)
  - Safety banner (sticky)
- **AI Editor [id]**
  - Per-platform publish-ready chips (Telegram / Threads / Reddit)
  - "Dry-run preview" button → drawer with computed payload
  - "Publishing disabled" badge when PUBLISHING_ENABLED=false
- **Approval Board**
  - 4 columns already exist (Pending, Approved, Published, Rejected) — extend to show `blocked` and `dry_run` jobs distinctly
- **Layout**
  - `ApiConnectionBadge` near topbar pill — shows "Connected" vs "Demo fallback"

## Verification commands

```bash
# backend
python -m pytest -q                                    # all green
python -m ruff check .                                 # clean

# frontend
pnpm -C apps/web run typecheck
pnpm -C apps/web run build                              # 13 routes

# smoke (with API running locally on :8000)
curl http://localhost:8000/readiness | head -c 400
curl http://localhost:8000/worker/status
curl -X POST http://localhost:8000/readiness/test-llm
curl -X POST http://localhost:8000/readiness/test-telegram-bot
curl -X POST http://localhost:8000/readiness/dry-run-publish/<candidate_id>

# deploy
cd apps/web && vercel --prod --yes
```

## Scope I will NOT do this pass

- Real Postiz publish flow (kept dry-run-by-default; user must enable explicitly)
- Multi-user / auth — still single-tenant local
- Backend deployment (FastAPI to Fly/Railway) — README will document the path
- Real Reddit/Threads OAuth token refresh — out of scope; basic readiness only
