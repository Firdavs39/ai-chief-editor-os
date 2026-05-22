# Phase 13 — Hosting decision

> Where to host the API + worker once they leave `localhost + cloudflared`.

Three options, ranked by my recommendation for an alpha operated by ONE
person (you). Decision is yours; this doc captures the trade-offs so you
can pick once and not revisit.

---

## Option A — Stay on home machine + Cloudflare quick tunnel

**Cost:** $0
**Uptime SLA:** ~95% (your machine is up when you're working)
**Effort:** zero (already running)

### When it's right
- Only one operator (you).
- Working hours overlap with when you'd publish anyway.
- You'd rather not pay $25–50/month for hosting yet.
- You haven't yet decided whether the product earns its rent.

### Limits
- If your machine reboots / sleeps, the tunnel + worker stop. Approvals
  queue up in DB until you're back. Acceptable for a one-person alpha.
- Cloudflared quick tunnels rotate URLs sometimes; long-lived URL needs
  a real Cloudflare account and a `cloudflared tunnel` (the persistent
  variant), not `cloudflared tunnel --url`.
- No Telegram-Bot webhook integration possible without a stable URL.

### Verdict
**Start here.** Migrate when you outgrow it, not before. The product is
designed to survive on this stack.

---

## Option B — Fly.io single-container

**Cost:** ~$5–15/month for a `shared-cpu-1x / 512mb` machine + 1 GB volume.
**Uptime SLA:** ~99.9% with auto-restart and health checks.
**Effort:** ~30 min once you have payment on Fly.

### Configs already drafted
- `fly.api.toml` — single-container with both uvicorn + worker, SQLite on
  a mounted volume (`/data/chief_editor.db`). Safe-default env (`MOCK_MODE=true`,
  `DRY_RUN_PUBLISH=true`, `PUBLISHING_ENABLED=false`).
- `infra/docker/fly-combined.Dockerfile` — referenced by the toml above.

### Deploy steps
1. `fly auth login` (one-time).
2. `fly launch --copy-config --no-deploy --name chief-editor-api`.
3. `fly volumes create chief_editor_data --size 1 --region fra` (or your region).
4. **`fly secrets set`** for each Vault-bound credential:
   ```
   MASTER_ENCRYPTION_KEY=...     # generate fresh; or copy from local .env
   ADMIN_TOKEN=...               # generate fresh
   # The following stay UNSET on Fly; operator pushes them via /secrets/* after deploy:
   #   ANTHROPIC_API_KEY, OPENAI_API_KEY,
   #   OLLAMA_BASE_URL, OLLAMA_API_KEY,
   #   REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
   #   TELETHON_API_ID, TELETHON_API_HASH,
   #   TELEGRAM_BOT_TOKEN, TELEGRAM_TARGET_CHANNEL_ID,
   #   POSTIZ_BASE_URL, POSTIZ_API_KEY
   ```
5. `fly deploy`.
6. Verify: `curl https://chief-editor-api.fly.dev/status`.
7. Provision integration credentials through the Vault endpoint (NOT via
   `fly secrets set`, so they remain encrypted-at-rest in Postgres and
   can rotate without redeploy).

### When it's right
- You publish daily and need uptime > "when my laptop is on".
- You want a stable public URL for the dashboard.
- You're ready to spend ~$10/month for peace of mind.

### Limits
- Single-container model means the worker can't scale separately. If
  generation becomes CPU-bound, split api/worker into two apps later.
- SQLite on the volume is fine up to a few thousand candidates. Beyond
  that, migrate to Managed Postgres (separate billing gate).

### Verdict
**Recommended once Phase 9 (first real publish) is working.** Not before —
running on Fly when you're still tuning gates wastes uptime budget.

---

## Option C — Railway / Render / Self-hosted Docker

**Cost:** ~$10–25/month depending on tier.
**Uptime SLA:** ~99.9%.
**Effort:** moderate (no pre-drafted configs).

### When it's right
- You already have a Railway / Render account and prefer that ecosystem.
- You want a simpler one-click deploy than Fly's CLI.

### Limits
- No pre-built configs in this repo. You'd write them.
- Railway's stateless-by-default model is awkward for the worker; you'd
  need a worker process running continuously.

### Verdict
**Pick only if you already use one of these.** Otherwise Option B has the
configs ready and the safety defaults baked in.

---

## What changes about safety on hosted environments

- **Same gates**: `PUBLISHING_ENABLED`, `DRY_RUN_PUBLISH`, approval-required.
- **Flag flipping is harder on Fly** — you can't just edit `.env`; you use
  `fly secrets set` which RESTARTS the machine. This is actually a
  feature: every flag change is auditable in `fly logs`.
- **Cloudflared tunnel must be turned off** when the same machine has Fly
  running on a different URL — otherwise you have two copies of the API
  writing to two different databases. Verify `cloudflared` is not running
  before deploying to Fly.
- **`MASTER_ENCRYPTION_KEY` rotation** is a `fly secrets set` away. The
  Vault supports MultiFernet (legacy keys) so rotation doesn't lose data.

---

## Migration path (Option A → Option B)

When you decide to migrate from home-machine to Fly:

1. **Drain**: stop accepting new generations on the home machine. Wait
   for in-flight runs to terminate.
2. **Backup local DB**: `cp chief_editor_live.db chief_editor_live.db.backup`.
3. **Export Vault data** (already encrypted): copy `integration_secrets`
   table rows. The same `MASTER_ENCRYPTION_KEY` will decrypt them on Fly.
4. **Provision Fly** following Option B steps.
5. **Restore DB**: `fly ssh sftp shell` → `put chief_editor_live.db /data/`.
6. **Verify**: visit `/status`, `/secrets/anthropic` (should show
   present:true), run one mock generation end-to-end.
7. **Switch DNS / tell Vercel**: update `NEXT_PUBLIC_API_URL` from the
   cloudflared URL to the fly.dev URL.
8. **Kill cloudflared**, kill the home-machine API and worker.
9. **Monitor**: `fly logs -a chief-editor-api` for the first day.

---

## My recommendation, today (May 19, 2026)

**Stay on Option A through Phase 9 (first real publish + 7 days of
observation).** If after that you're publishing daily and the
home-machine downtime is annoying, migrate to Option B.

The 7-day Phase-9 observation also stress-tests whether daily publishing
is actually a habit you want — if you fall off after 3 days, hosting on
Fly was an avoidable $10/month.

Don't pay for uptime you're not yet using.
