# Integration Secrets Vault

> Encrypted-at-rest credential storage for the seven supported integrations,
> drivable from Settings → **Integrations vault** without touching `.env`.

## What it is (and what it is not)

The vault lets an operator save, rotate, test, and delete API credentials for:

- Ollama / Kimi K2.6
- Anthropic
- OpenAI
- Telegram bot (publish)
- Telethon (monitor)
- Reddit (read-only)
- Postiz (Threads / Reddit publish)

The vault is **not** a substitute for `.env`. Environment variables always win.
If `ANTHROPIC_API_KEY` is set in `.env`, the saved-in-vault value is ignored.

The vault does **not** change anything about the publishing pipeline. All
existing safety gates (`DRY_RUN_PUBLISH`, `PUBLISHING_ENABLED`, approval
gate, mock-mode fallback) keep working unchanged.

## Security model

| Property | Guarantee | Enforcement |
|---|---|---|
| Encryption at rest | Fernet (AES-128-CBC + HMAC-SHA256) via `cryptography`. Multi-key reads via `MultiFernet`. | `services/secrets/crypto.py` |
| No plaintext in API | GET responses contain only length + last-4 mask (secrets) or value (non-secret config fields like URL/model). | `apps/api/app/routers/secrets.py::_build_summary` |
| No plaintext in logs | `SystemLog.data` for `vault.*` events is restricted to a whitelisted key set. | `_audit()` in router |
| No plaintext in DB | `IntegrationSecret.encrypted_value` is always a Fernet token; no companion plaintext column exists. | DB model |
| No plaintext in client | Frontend never receives values. Inputs never pre-fill. | `provider-card.tsx` |
| Admin token compare | Constant-time `secrets.compare_digest` (imported as `stdlib_secrets`). | `apps/api/app/deps.py::require_admin_token` |
| Auth on every endpoint | All `/secrets/*` calls (including GET) require `X-Admin-Token` whenever the API can be reached non-locally. | `require_admin_token` dependency on router |
| No localStorage for token | Admin token lives only in React state — refresh clears it. | `integrations-vault.tsx` |
| No publishing from tests | Per-provider `/secrets/{provider}/test` calls reuse identity probes (Telegram `getMe`, Postiz `/health`, OAuth issuance, JSON-only LLM probes). They never call `sendMessage`, never POST to Postiz `/api/posts`, never submit Reddit content. | `_probe_*` functions in `routers/secrets.py` |

### Environment variables

```dotenv
# Primary key used to encrypt new writes and decrypt existing rows.
MASTER_ENCRYPTION_KEY=

# Comma-separated old keys (for read-only decryption during a rotation).
# Drop entries here once `rotate-key` has re-encrypted every row.
MASTER_ENCRYPTION_KEYS_LEGACY=

# Required on every /secrets/* request via X-Admin-Token header,
# unless running strictly local dev (see "Admin token" below).
ADMIN_TOKEN=
```

### Generate a key

```bash
python -m chief_editor.services.secrets generate-key
# Prints e.g. 4f9oW...= (base64). Paste into .env as MASTER_ENCRYPTION_KEY.
```

⚠️ **If you lose `MASTER_ENCRYPTION_KEY`, every saved secret becomes
unreadable.** Back the value up in your password manager / secrets store. The
app does not crash — the resolver downgrades undecryptable rows to "missing"
and logs `vault.decrypt_failed` (no token, no plaintext).

## Resolution order

For every field, the resolver walks this priority list:

1. **Env var** — read via the pydantic `Settings` attribute matching the
   schema's `env_var` (e.g. `ANTHROPIC_API_KEY` → `settings.anthropic_api_key`).
2. **Vault** — decrypt the row at `(provider, key_name)`. If decryption fails
   (master key rotated without `MASTER_ENCRYPTION_KEYS_LEGACY` set), treat as
   missing and log `vault.decrypt_failed`.
3. **Missing** — provider stays unconfigured. Mock fallback kicks in if
   `MOCK_MODE=true`.

The aggregate per-provider source is one of `env`, `vault`, `env+vault`,
`missing`. The readiness UI badge reflects it.

## Admin token

All `/secrets/*` endpoints require `X-Admin-Token`. There is **one** narrow
exemption (strict local dev) where the header may be omitted, and it requires
every condition below to hold simultaneously:

- `APP_ENV=dev`
- `LIVE_MODE=false`
- `PUBLIC_API_URL` is empty
- The request's client host AND `Host:` header are loopback (`localhost`,
  `127.0.0.1`, `::1`, `0.0.0.0`, `host.docker.internal`)
- `FRONTEND_ORIGIN` is empty OR every entry begins with
  `http(s)://localhost` / `http(s)://127.0.0.1`

If any condition fails, missing/invalid token → HTTP 401.

In our current Cloudflare-tunneled alpha, **`ADMIN_TOKEN` is mandatory** — the
public host and a non-empty `PUBLIC_API_URL` disable the exemption.

The admin token is compared with `secrets.compare_digest` (imported as
`stdlib_secrets` to avoid clashing with `chief_editor.services.secrets`).

## Frontend behavior (memory-only token)

1. The Settings page shows the **Integrations vault** section locked by
   default.
2. The operator pastes their `ADMIN_TOKEN` into an inline input and clicks
   **Unlock**.
3. The token is held in React state for the component lifetime. The input
   field is cleared after unlock so the value is not sitting in the DOM.
4. On reload, navigation away, or `Lock`, the token disappears.
5. **No** token is written to `localStorage`, `sessionStorage`, cookies, or
   the URL.
6. The vault never returns secret values, so input fields render with
   `placeholder="•••••• configured — type to replace"` and stay empty.

## Test endpoints — what they actually do

| Provider | Probe | Publishes? |
|---|---|---|
| anthropic | `complete_json` with `{"ok": true}` schema | no |
| openai | same | no |
| ollama | same against the configured base URL | no |
| telegram_bot | HTTP GET `/getMe` only | no |
| telethon | presence-only check (interactive login is CLI-only) | no |
| reddit | OAuth `client_credentials` token issuance | no |
| postiz | GET `/api/v1/integrations` or `/api/posts?limit=1` | no |

After each test the per-provider rows store `status`, `last_tested_at`, and a
truncated `last_test_message`. The LLM provider cache is reset on writes/tests
so the next real call rebuilds with the fresh credentials.

## Key rotation

```bash
# 1. Generate the new key. Keep the old one around for one deploy.
python -m chief_editor.services.secrets generate-key

# 2. Update .env:
#    MASTER_ENCRYPTION_KEY=<new>
#    MASTER_ENCRYPTION_KEYS_LEGACY=<old>

# 3. Restart the API.

# 4. Rewrite every row with the new key.
python -m chief_editor.services.secrets rotate-key

# 5. Once successful, remove MASTER_ENCRYPTION_KEYS_LEGACY and restart again.
```

`rotate-key` decrypts each row using `MultiFernet` (so any key in the list
works), then re-encrypts with the *primary* key. Rows that cannot be decrypted
by any configured key are reported on stderr and the process exits non-zero.

## Alpha limitations

- **Single tenant.** There is no `user_id` column on `IntegrationSecret`.
  Anyone with the admin token sees every saved value's mask.
- **Shared admin token.** Only one token, one role, no rotation primitives in
  the UI.
- **Telethon session file is not stored.** Only `api_id` / `api_hash` go in
  the vault. The interactive session login still has to be done via the CLI.
- **No per-secret audit trail.** `SystemLog` records the *event* (saved,
  deleted, tested) but not "who" since there is no concept of users yet.

## SystemLog discipline

`SystemLog.data` bypasses the structlog redactor. The vault code therefore
restricts payloads to a whitelist:

```
provider, key_name, length, is_secret, source, status,
reason, fields_written, fields_deleted, rows_deleted, host, client_host
```

No `value`, no `token`, no `encrypted_value`. The whitelist is enforced in
`apps/api/app/routers/secrets.py::_audit`. Tests in
`tests/test_secrets_vault_safety.py::test_no_secret_substring_in_systemlog_after_full_cycle`
sweep every row after a full save/test/delete cycle and assert no plaintext
substring appears in any field.

## API contract

```
GET    /secrets/integrations          → {vault_enabled, admin_token_required, providers}
GET    /secrets/{provider}            → ProviderSummary
POST   /secrets/{provider}            body: {values: {key_name: value, …}}
                                      empty value → delete that row
DELETE /secrets/{provider}/{key_name} → removes one row
POST   /secrets/{provider}/test       → ReadinessItem (same shape readiness UI renders)
```

Every endpoint requires `X-Admin-Token` (see *Admin token* above). Missing
`MASTER_ENCRYPTION_KEY` → write/delete return HTTP 409 with
`detail.reason = "missing_master_key"`.
