# CLAUDE.md — AI Chief Editor OS

## Product Vision

AI Chief Editor OS is a premium AI content intelligence platform. It watches selected sources (Telegram channels, Reddit communities, Threads-ready sources, RSS / manual feeds), detects rising trends, explains *why* they matter, generates ready-to-post content in the user's style, presents approval cards, schedules and publishes via a real publishing layer, and learns from performance over time.

It is a dashboard-first product. Telegram exists only as an optional notification / approval channel — **not** as the primary interface.

The bar is Sprout Social / Hootsuite functionality with Linear / Raycast / Vercel polish.

## Architecture

```
apps/
  web/      Next.js 15 dashboard (App Router, TS, Tailwind, shadcn-style)
  api/      FastAPI backend (Python 3.12 in Docker)
  worker/   async worker (collectors + AI generation + publisher dispatch)
packages/
  shared/   importable Python package `chief_editor` used by api + worker
infra/
  docker/   Dockerfiles for api, worker, web
```

Single Python project at the root (`pyproject.toml`). All Python code imports from `chief_editor` (the shared package), `app` (FastAPI), or `worker` (worker entry).

Services run via `docker compose up`: `postgres`, `redis`, `api`, `worker`, `web`.

## Commands

```bash
make install              # pip install -e .[dev]  +  pnpm install in apps/web
make dev                  # show local-dev commands for 3 terminals
make test                 # pytest -q
make lint                 # ruff check + next lint
make seed                 # populate demo data
make docker-up            # docker compose up -d --build
make docker-down
make smoke                # curl key endpoints
```

Local dev (without Docker):
```bash
uvicorn app.main:app --reload --app-dir apps/api --port 8000
python -m worker.main
cd apps/web && pnpm dev
```

Open `http://localhost:3000` for the dashboard, `http://localhost:8000/docs` for the API.

## Coding Rules

1. **No publish without approval.** Every code path that produces an outbound post must check `ApprovalDecision.decision == "approve"` before dispatch. Both the API route and the publisher itself assert this — defense in depth.
2. **No TODO placeholders.** No `pass  # later`, no `raise NotImplementedError`, no empty modules. Every file ships working behavior.
3. **No unauthorized scraping.** Telegram via Telethon only against channels the user has access to. Reddit via official API. Threads only via Postiz or official Threads API. No HTML scraping fallbacks.
4. **Mock fallbacks.** If credentials for any external service are missing, the corresponding adapter falls back to mock and logs a `SystemLog` event. The product must run end-to-end in demo mode with **zero** external keys.
5. **Russian-first generated content.** All AI-generated post bodies, demo candidates, demo trends, style profile examples, critic notes, and demo system logs are in Russian. UI labels stay English (premium SaaS convention).
6. **Deterministic mock LLM.** The mock provider must return valid JSON conforming to the requested schema. Tests rely on this.
7. **Transparent scoring.** Trend scores expose every component (`recency`, `engagement`, `source_weight`, `novelty`, `controversy`, `usefulness`, `style_fit`) and the weighted total.
8. **No plain tables as the primary UI.** Use cards, boards, drawers, score panels.

## UI Quality Bar

- Deep black / charcoal background (#08090d base) with layered radial glow
- Soft glass panels: `bg-white/[0.03]` + `backdrop-blur-xl` + `border-white/[0.08]`
- Subtle violet (#8b5cf6) + cyan (#22d3ee) accents, used for emphasis only
- Left icon rail + secondary nav (Linear-style)
- Kanban approval board, floating analytics widgets, score breakdown bars
- Premium typography (Inter + JetBrains Mono for numerics)
- Skeleton and empty states everywhere
- Looks like a product someone would pay for. Not an admin template.

## Module Map

- **Command Center** → `/dashboard` (apps/web/app/(app)/dashboard)
- **Trend Radar** → `/trends`
- **AI Editor** → `/editor` and `/editor/[id]`
- **Approval Board** → `/approvals`
- **Content Calendar** → `/calendar`
- **Sources** → `/sources`
- **Style DNA** → `/style-dna`
- **Analytics** → `/analytics`
- **Settings** → `/settings`

## External Adapters (real + mock pairs)

| Service | Real adapter | Falls back to |
|---|---|---|
| LLM | `AnthropicProvider` / `OpenAIProvider` | `MockLLMProvider` |
| Telegram collect | Telethon (`TELETHON_API_*`) | `MockCollector` |
| Reddit collect | `asyncpraw` (`REDDIT_CLIENT_*`) | `MockCollector` |
| RSS collect | `feedparser` (no creds) | always real |
| Telegram publish | `python-telegram-bot` (`TELEGRAM_BOT_TOKEN`) | `MockPublisher` |
| Postiz publish | `POSTIZ_BASE_URL` + `POSTIZ_API_KEY` | `MockPublisher` |
| Threads publish | Postiz integration | `MockPublisher` |

## Demo Mode

`MOCK_MODE=true` + `LLM_PROVIDER=mock` (defaults in `.env.example`). Run `make seed` or `POST /demo/seed` to populate realistic Russian demo content (sources, trends, candidates, approvals, calendar, analytics).
