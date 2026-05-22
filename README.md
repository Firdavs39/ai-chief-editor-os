# AI Chief Editor OS

A premium dashboard-first AI content intelligence platform. It watches sources you care about (Telegram channels, Reddit communities, RSS feeds, Threads via Postiz), spots emerging trends, explains why each one matters, writes style-matched posts, presents approval cards, schedules and publishes through a real publishing layer, and learns from performance.

Think Sprout Social / Hootsuite functionality with Linear / Raycast / Vercel polish.

## Highlights

- **Dashboard first.** Telegram is only an optional notification channel — the product is a web app.
- **Trend Radar with transparent scoring.** Every cluster shows its recency / engagement / novelty / controversy / usefulness / style-fit breakdown.
- **AI Editor with critic agent.** Candidates ship with Telegram, Threads, and Reddit versions, a psychology hook, a CTA, and critic notes (slop risk, weak hook, length, controversy, etc.).
- **Approval-gated publishing.** No post leaves the system without an `ApprovalDecision`. Defense in depth — both the API and the publisher re-check.
- **Integration Secrets Vault.** Add API keys (Ollama, Anthropic, OpenAI, Telegram, Reddit, Postiz) from Settings without editing `.env`. Encrypted at rest with Fernet + admin-token gating. See [docs/SECRETS_VAULT.md](docs/SECRETS_VAULT.md).
- **Real + mock adapters everywhere.** Works end-to-end with zero external keys; swap in real keys to enable real publishing and collection.
- **Russian-first generated content.** Demo seed, candidate copy, style DNA, and critic notes are Russian by default. UI labels stay English.

## Phase status (May 2026)

| Phase | Status | What it adds |
|---|---|---|
| 0–5 | ✅ shipped | Foundation, polish, Live-Mode readiness, deploy runtime, real LLM (Ollama Kimi K2.6) |
| 5.1 | ✅ shipped | Reproducibility audit — surfaced editorial_rationale length-overflow on Kimi |
| 5.2 | ✅ shipped | Schema raised to platform-real limits; validation-aware repair; length observability. 19 new tests. |
| 6 | ✅ code shipped, ready to run | Reproducibility batch script on Kimi + token telemetry on every step. `LLM_PROVIDER_FALLBACK` setting exists but is dormant by default — **Kimi-only stack**, no second LLM provider on the roadmap. 8 new tests. |
| 7 | ✅ scripts shipped, awaits REDDIT_*/TELETHON_* creds | RSS+Reddit+Telegram source wiring. 5 AST guards. |
| 8 | ✅ walker shipped, awaits test channel | Operator-driven safety rehearsal — every gate verified in DB. |
| 9 | ⏳ operator task | First real publish + 7-day observation |
| 10 | ✅ scaffold shipped | `/analytics/cost` + price table. 9 new tests. |
| 11–12 | ✅ scaffolds shipped | Style DNA proposals (no silent mutation) + performance feedback (capped boost). 10 new tests. |
| 13 | ✅ documented | Hosting decision (see [docs/HOSTING_DECISION.md](docs/HOSTING_DECISION.md)) |

See [docs/PHASE_PLAN.md](docs/PHASE_PLAN.md) for the full roadmap, [docs/HANDOFF.md](docs/HANDOFF.md) for what's done vs operator-action items, and [docs/OPERATOR_RUNBOOK.md](docs/OPERATOR_RUNBOOK.md) for the 4-step publish ritual.

## Architecture

```
apps/web      Next.js 15 dashboard (App Router, TypeScript, Tailwind)
apps/api      FastAPI backend
apps/worker   async collectors + AI generation + publisher dispatch
packages/shared/chief_editor   shared Python package (models, services, llm, publishing, collectors)
infra/docker  Dockerfiles for api / worker / web
```

Stack: Python 3.12 · FastAPI · SQLModel · PostgreSQL 16 · Redis 7 · Next.js 15 · TypeScript · Tailwind · shadcn-style primitives · lucide-react · recharts · react-flow.

## Run locally with Docker (recommended)

```bash
cp .env.example .env
make docker-up
```

Then open:
- Dashboard → http://localhost:3000
- API docs → http://localhost:8000/docs

To seed demo data after the stack is healthy:
```bash
curl -X POST http://localhost:8000/demo/seed
```

Stop:
```bash
make docker-down
```

## Run locally without Docker

You'll need Postgres and Redis running locally (or change `DATABASE_URL` to SQLite for quick experiments).

```bash
# 1. Python deps
python -m pip install -e ".[dev]"

# 2. Web deps
cd apps/web && pnpm install && cd ../..

# 3. Start in three terminals
uvicorn app.main:app --reload --app-dir apps/api --port 8000
python -m worker.main
cd apps/web && pnpm dev
```

Then `curl -X POST http://localhost:8000/demo/seed` to populate demo content.

## Demo mode

Defaults in `.env.example`:
- `MOCK_MODE=true`
- `LLM_PROVIDER=mock`

No external API keys required. All collectors fall back to a mock corpus, the LLM provider returns deterministic Russian copy, and the publisher logs to `SystemLog` instead of hitting any external service. Every UI page shows seeded content; the worker keeps the data refreshing.

A persistent **MOCK MODE** badge is visible in the dashboard so the demo state is intentional and obvious.

## Connecting real services later

| Capability | Required env vars | Adapter |
|---|---|---|
| Anthropic LLM | `ANTHROPIC_API_KEY`, `LLM_PROVIDER=anthropic` | `chief_editor.llm.anthropic_provider` |
| OpenAI LLM | `OPENAI_API_KEY`, `LLM_PROVIDER=openai` | `chief_editor.llm.openai_provider` |
| Telegram collect | `TELETHON_API_ID`, `TELETHON_API_HASH` | `chief_editor.collectors.telegram` |
| Reddit collect | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | `chief_editor.collectors.reddit` |
| RSS | none (always works) | `chief_editor.collectors.rss` |
| Telegram publish | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_TARGET_CHANNEL_ID` | `chief_editor.publishing.telegram` |
| Postiz publish | `POSTIZ_BASE_URL`, `POSTIZ_API_KEY` | `chief_editor.publishing.postiz` |

Set the relevant vars and restart. Missing credentials always degrade to mock with a `SystemLog` warning — the product never silently fails.

You can also add any of these credentials from the **Settings → Integrations vault** UI instead of editing `.env`. Generate a `MASTER_ENCRYPTION_KEY` with `python -m chief_editor.services.secrets generate-key`, set `ADMIN_TOKEN`, and use the unlock form in the vault section. Env always takes priority. See [docs/SECRETS_VAULT.md](docs/SECRETS_VAULT.md).

Threads publishing is routed through Postiz (or the official Threads API once available). **No unofficial scraping.**

## Safety rule

> **Nothing is published without an explicit `ApprovalDecision`.**
> The API route refuses to create a `PublishJob` without one. The worker re-validates before dispatch. The publisher's `publish()` method asserts again at the boundary.

## Quality gates

```bash
make test     # pytest -q
make lint     # ruff + next lint
```

Tests cover settings loading, ORM models, dedup, trend scoring breakdown, mock collector, mock LLM, candidate generation flow, critic checks, the approval gate, the mock publisher, and `/health`.

## Known limitations

- Single-tenant local MVP — no auth, no multi-user, no billing.
- Auto-create tables on startup via `SQLModel.metadata.create_all`; production migrations (Alembic) are out of scope here.
- Mobile breakpoint is graceful but the design is optimized for ≥1280 viewport.
- Real-time collaboration / multi-actor approvals are not wired yet.
- Analytics in demo mode is mock data — real metrics require connected publishers reporting back.

## Module map

- Command Center → [/dashboard](apps/web/app/(app)/dashboard/page.tsx)
- Trend Radar → [/trends](apps/web/app/(app)/trends/page.tsx)
- AI Editor → [/editor](apps/web/app/(app)/editor/page.tsx)
- Approval Board → [/approvals](apps/web/app/(app)/approvals/page.tsx)
- Content Calendar → [/calendar](apps/web/app/(app)/calendar/page.tsx)
- Sources → [/sources](apps/web/app/(app)/sources/page.tsx)
- Style DNA → [/style-dna](apps/web/app/(app)/style-dna/page.tsx)
- Analytics → [/analytics](apps/web/app/(app)/analytics/page.tsx)
- Settings → [/settings](apps/web/app/(app)/settings/page.tsx)
