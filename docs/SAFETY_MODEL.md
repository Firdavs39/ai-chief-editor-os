# Safety model

AI Chief Editor OS enforces three independent gates between an AI-generated
draft and a real external post. Each gate is configured by environment
variables and validated in code at a different layer.

## State machine

```
draft ─── review ──▶ approved ─── worker tick ──▶ blocked | dry_run | pending_config | running ──▶ done | failed
                                       │
                                       └── (any failure path also logs SystemLog)
```

Job statuses produced by the new safety layer:

| Status | Meaning | Set by |
|---|---|---|
| `pending` | Approved, waiting for scheduled dispatch | `approve_and_schedule()` |
| `blocked` | `PUBLISHING_ENABLED=false` — master switch off | worker `_dispatch_one()` |
| `dry_run` | `DRY_RUN_PUBLISH=true` — payload computed, nothing sent | worker `_dispatch_one()` |
| `pending_config` | Live mode but publisher isn't configured for the platform | worker `_dispatch_one()` |
| `running` | Worker called publisher | worker `_dispatch_one()` |
| `done` | Publisher returned success | worker `_dispatch_one()` |
| `failed` | Publisher returned error or approval check failed | worker `_dispatch_one()` |

## Three layers of approval enforcement

1. **API route** — `POST /publishing/jobs` refuses to create a job for a
   candidate that has no `approve` decision.
2. **Worker dispatch** — `_dispatch_one()` re-checks the approval decision
   before doing anything else, even if the row was created in some other path.
3. **Publisher boundary** — `Publisher.publish()` (`MockPublisher`,
   `TelegramPublisher`, `PostizPublisher`) raises `ApprovalRequiredError`
   when the decision passed in is missing or not `approve`.

## The five mode flags

| Flag | Default | Purpose |
|---|---|---|
| `DEMO_MODE` | `true` | Dashboard shows demo/fallback content where helpful |
| `MOCK_MODE` | `true` | Adapters degrade to mock when creds are missing |
| `LIVE_MODE` | `false` | UI surfaces real-config expectations and errors |
| `DRY_RUN_PUBLISH` | `true` | Publisher computes payload but does NOT contact services |
| `PUBLISHING_ENABLED` | `false` | Master kill switch — required for any real publish |

Both `DRY_RUN_PUBLISH=true` **and** `PUBLISHING_ENABLED=false` block any real
publish. The path to a real send is intentionally narrow:

```
PUBLISHING_ENABLED=true  AND  DRY_RUN_PUBLISH=false  AND  approval=approve  AND  publisher configured
```

If any of these is false the job ends up in `blocked`, `dry_run`, or
`pending_config`. None of these terminal states publish.

## Secrets policy

- API keys, tokens, and session names are read from environment variables.
- They MAY be persisted in the database via the **Integration Secrets Vault**,
  but only as Fernet ciphertext (AES-128-CBC + HMAC-SHA256). Plaintext
  storage is never permitted. See [docs/SECRETS_VAULT.md](SECRETS_VAULT.md).
- They are **never** returned to the frontend. Readiness endpoints emit only
  presence and length (`{present: true, length: 51}`) — never the value itself
  or a prefix/suffix. The vault returns the same safe metadata plus a last-4
  mask, never the underlying value.
- They are **never** logged in plaintext. `SystemLog` rows carry only metadata
  (provider, key_name, length, status, source). The vault's audit helper
  whitelists payload keys at the call site because `SystemLog.data` bypasses
  the structlog redactor.

### Encrypted credentials at rest (Secrets Vault)

- `MASTER_ENCRYPTION_KEY` must be set to enable the vault. If absent, the
  app still runs — env-based credentials work normally and the vault simply
  refuses writes with HTTP 409.
- Every value is stored as a `MultiFernet` token. Key rotation is supported
  via `MASTER_ENCRYPTION_KEYS_LEGACY` + the `rotate-key` CLI.
- Env vars always take priority. The resolver consults the vault only when
  the corresponding env var is empty.
- All `/secrets/*` endpoints (including GET) require `X-Admin-Token`. The
  only exception is strictly local dev — see SECRETS_VAULT.md for the exact
  conditions, all of which must hold simultaneously.
- The frontend keeps the admin token in React memory only. It is never
  written to `localStorage`, `sessionStorage`, cookies, or the URL.

## What the test endpoints are allowed to do

- `POST /readiness/test-llm` — single tiny structured-JSON ping.
- `POST /readiness/test-telegram-bot` — `getMe`. Optionally `getChat` for the
  target channel. **No `sendMessage`.**
- `POST /readiness/test-telethon` — checks presence of API ID/HASH and session
  file. **Does not log in.**
- `POST /readiness/test-reddit` — OAuth `client_credentials` grant. **No
  comments, no posts, no votes.**
- `POST /readiness/test-postiz` — GET against a Postiz read endpoint. **No
  `POST /api/posts`, no scheduling, no integration mutation.**
- `POST /readiness/test-source/{id}` — RSS fetches the feed XML; TG/Reddit
  sources just check creds.
- `POST /readiness/dry-run-publish/{id}` — computes the payload that would be
  sent and returns it. **Never calls the publisher.**
- `POST /secrets/{provider}/test` — same identity/read-only probes as the
  matching `/readiness/test-*` endpoint, but uses credentials resolved from
  env-or-vault. **Same rules: no `sendMessage`, no Postiz `POST /api/posts`,
  no Reddit comments/posts/votes.** Tests in `test_secrets_vault_safety.py`
  patch the publishers and assert zero dispatch calls.

## What the worker is allowed to do

- Run collector loop (per source, per the source's adapter).
- Run generation loop (LLM via the configured provider).
- Run publisher loop, but **only** through `_dispatch_one()` which enforces:
  1. candidate exists
  2. approval exists and is `approve`
  3. `PUBLISHING_ENABLED=true`
  4. `DRY_RUN_PUBLISH=false`
  5. publisher resolved for the platform is not `MockPublisher` (unless
     `MOCK_MODE=true` was set explicitly)
  6. then — and only then — `publisher.publish()` is called.

## Disallowed at every level

- Unofficial Threads scraping.
- Reddit access without an explicit user-agent and OAuth.
- Telegram client-side posting (publishing is Bot API only; Telethon is
  read-only).
- Returning secret values via any endpoint.
- Storing API keys in the database.
- Silently sending an approved post when the publisher is missing.

## Regression-test coverage

These tests guard the surfaces that an operator (or the worker) touches when
approving / rejecting / dry-running, and they re-assert the safety invariants
at the HTTP boundary — the layer Vercel hits.

| File | What it locks down |
|---|---|
| `tests/test_approval_gate.py` | publisher refuses to send without an `approve` decision; reject path; mock publisher with valid approval |
| `tests/test_publishing_safety.py` | worker `_dispatch_one()` honours `PUBLISHING_ENABLED`, `DRY_RUN_PUBLISH`, missing-publisher, missing-approval |
| `tests/test_publishing_safety_http.py` | `/readiness/dry-run-publish` returns `would_send=false` by default; approve → worker tick chain leaves candidate **approved**, never **published**, while publishing is disabled or in dry-run |
| `tests/test_approval_serialization.py` | `POST /approvals/{id}/approve` and `/reject` return full candidate + job payloads (regression for the SQLModel-post-commit `model_dump()` bug — they used to 500) |
| `tests/test_readiness.py` | `/readiness` never crashes on missing config; no secret substrings leak |
| `tests/test_cors_and_settings.py` | safety flag defaults are safe (no `publishing_enabled && !dry_run_publish` combination by default); logging redactor masks secret-shaped keys |

### Approval response does not imply real publishing

A successful HTTP 200 on `POST /approvals/{id}/approve` means **the operator's
intent was recorded**: an `ApprovalDecision(decision="approve")` row exists
and a `PublishJob(status="pending")` row was created. It does **not** mean
anything left the box. The worker is what dispatches — and the worker honours
all three gates. The HTTP response is a receipt, not a delivery.

If the worker can't dispatch (publishing disabled, dry-run, publisher missing),
the job ends up in a terminal `blocked` / `dry_run` / `pending_config` state.
The candidate stays at `status="approved"`. Real `"published"` requires the
publisher's `publish()` to return success, which only happens when every gate
is green simultaneously.
