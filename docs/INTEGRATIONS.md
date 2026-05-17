# Integrations

How each external service is wired in, what credentials it needs, and what
the readiness probe does.

> **Two ways to provide credentials**
>
> 1. `.env` (priority) — the variables documented in each section below.
> 2. **Integration Secrets Vault** (fallback) — encrypted-at-rest storage
>    drivable from Settings → Integrations vault. Env always wins; vault
>    fills the gaps. See [SECRETS_VAULT.md](SECRETS_VAULT.md).

## LLM

### Anthropic

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-…
```

- Adapter: `chief_editor.llm.anthropic_provider.AnthropicProvider`
- Default model: `claude-opus-4-7` (override with `ANTHROPIC_MODEL`)
- Readiness probe: trivial `{"ok": true}` JSON completion. Validates the
  response is parseable JSON and contains the key.

### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-…
```

- Adapter: `chief_editor.llm.openai_provider.OpenAIProvider`
- Default model: `gpt-4o` (override with `OPENAI_MODEL`)
- Readiness probe: same trivial JSON ping.

### Mock

`LLM_PROVIDER=mock` (or any provider with missing key while `MOCK_MODE=true`)
falls back to `MockLLMProvider` — a deterministic Russian-first generator
used in tests and demos.

### Ollama / Kimi K2.6 (OpenAI-compatible)

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=https://ollama.com         # or http://localhost:11434 for local
OLLAMA_API_KEY=ollama_…                    # required for remote; optional for local
OLLAMA_MODEL=kimi-k2.6:cloud               # any model name your endpoint serves
```

- Adapter: `chief_editor.llm.ollama_provider.OllamaProvider`
- Wire format: OpenAI Chat Completions (Ollama exposes this at `/v1/chat/completions`).
- Uses the official `openai` Python SDK with a custom `base_url` — same retry +
  JSON-repair path as the OpenAI provider.
- **Local Ollama**: when `OLLAMA_BASE_URL` is `http://localhost:11434` /
  `http://127.0.0.1:11434` and `OLLAMA_API_KEY` is empty, the registry uses the
  documented sentinel token `ollama` automatically. You don't need to invent a key.
- **Ollama Cloud**: a real API key is required. Generate one at
  https://ollama.com/settings/keys. **Never paste it into chat or commit it.**
- Readiness probe: trivial structured-JSON ping using `complete_json` with a
  `{"ok": true, "provider": "ollama"}` schema; validates response shape.
- Streaming and multimodal inputs are intentionally not used in this stage.
- If the API runtime is on Vercel / Fly / etc. and Ollama is local, expose
  Ollama via a tunnel (e.g. cloudflared, ngrok) — the API must be able to
  reach `OLLAMA_BASE_URL` over HTTPS.

## Telegram

There are **two** Telegram surfaces — keep them straight:

### Bot API — publishing only

```env
TELEGRAM_BOT_TOKEN=…           # from @BotFather
TELEGRAM_TARGET_CHANNEL_ID=…   # @handle or -100… numeric id
TELEGRAM_OWNER_ID=…            # optional, for notifications
```

- Adapter: `chief_editor.publishing.telegram.TelegramPublisher`
- Library: `python-telegram-bot` v21
- Readiness probe: `GET https://api.telegram.org/bot{TOKEN}/getMe`. Validates
  `ok: true` and returns the bot username.
- **Never** sends a test message from the web. The probe is bot identity only.

Setup:

1. Open @BotFather → `/newbot` → follow prompts.
2. Add the bot to your channel as an admin (you need to be the channel owner).
3. Get the channel id by forwarding a message from the channel to @userinfobot
   or via `getChat`.

### Telethon — read-only monitoring

```env
TELETHON_API_ID=…
TELETHON_API_HASH=…
TELETHON_SESSION_NAME=chief_editor_session
```

- Adapter: `chief_editor.collectors.telegram.TelegramCollector`
- Library: `telethon` 1.x
- Readiness probe: presence of API ID + HASH **and** of the session file.
- The session is created via an **interactive** CLI flow — the web cannot do
  it (2FA / code entry). Run the bootstrap once locally:

```bash
python -c "from telethon import TelegramClient; \
  TelegramClient('chief_editor_session', YOUR_API_ID, 'YOUR_API_HASH').start()"
```

Telethon is for monitoring channels you are a member of. It is **not** used
to send messages — that's the Bot API path.

## Reddit

```env
REDDIT_CLIENT_ID=…
REDDIT_CLIENT_SECRET=…
REDDIT_USER_AGENT=my-app/1.0 by your_reddit_handle
```

- Adapter: `chief_editor.collectors.reddit.RedditCollector`
- Library: `asyncpraw`
- Setup: create a script app at https://www.reddit.com/prefs/apps.
- User-agent **must** identify your app and include a contact. Reddit rate-
  limits or blocks generic strings.
- Readiness probe: `POST https://www.reddit.com/api/v1/access_token` with
  `client_credentials`. Returns an access token if OK.
- Publishing through Reddit goes via Postiz, not directly through this
  collector.

## Postiz

```env
POSTIZ_BASE_URL=https://postiz.example.com
POSTIZ_API_KEY=…
POSTIZ_THREADS_INTEGRATION_ID=…
POSTIZ_REDDIT_INTEGRATION_ID=…
```

- Adapter: `chief_editor.publishing.postiz.PostizPublisher`
- Postiz is our **only** path to Threads (no unofficial scraping) and our
  cross-platform Reddit publisher.
- Each platform needs its `INTEGRATION_ID` configured. The id is available
  inside Postiz once the integration is connected.
- Readiness probe tries (in order) `/api/v1/integrations`, `/api/integrations`,
  `/api/posts?limit=1` — first 2xx wins. **No POST** in the probe.
- Real post creation in `PostizPublisher._dispatch` sends `POST /api/posts`
  with `integrationId`, `scheduleAt`, and `post: [{value: body}]`.

## RSS

No credentials. `feedparser` reads the feed URL.

## Threads

Threads is **only** reachable via Postiz in this MVP. We do not scrape
threads.net. If the official Threads API becomes generally available, it
can be wired in as another `Publisher` subclass — but until then Postiz is
the supported path.
