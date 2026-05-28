"""Phase 7 — interactive Telethon session-file builder.

You run this ONCE on your local machine. Telegram sends you a 5-digit SMS
code that you type into the prompt; the session string is written to disk
encrypted under your filesystem permissions. Claude (the AI assistant)
must NOT see the phone number or the SMS code — they're handled entirely
by the local Telethon library and your stdin.

Pre-requisites:
1. You've registered an app at https://my.telegram.org (instant, free).
2. You've POSTed `api_id` and `api_hash` to `/secrets/telethon/*` in the
   running API — this script reads them from the Vault, not from chat.
3. You have a Telegram account on the phone number you're about to use.

Usage:
    python -m scripts.create_telethon_session

The script will:
- Read api_id + api_hash from the Vault (refusing if not configured).
- Prompt you for your phone number locally.
- Ask Telegram to send an SMS code.
- Prompt you for the code locally.
- Write the session to `data/telethon/<session_name>.session`.

NOTHING about the phone, code, or session content is logged or printed
beyond the minimum needed to confirm success.
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

# Local module imports — assumes PYTHONPATH includes packages/shared.
try:
    from chief_editor.services.integration_config import resolve_provider
    from chief_editor.settings import get_settings
except ImportError:
    print(
        "Could not import chief_editor — ensure PYTHONPATH is set:\n"
        '  $env:PYTHONPATH = "packages/shared;apps/api;apps/worker"',
        file=sys.stderr,
    )
    raise


def main() -> int:
    try:
        from telethon import TelegramClient  # type: ignore
    except ImportError:
        print(
            "telethon package not installed. Install via:  pip install telethon",
            file=sys.stderr,
        )
        return 1

    settings = get_settings()
    if not settings.vault_enabled:
        print(
            "Vault is not enabled (MASTER_ENCRYPTION_KEY missing). "
            "Cannot read telethon credentials securely.",
            file=sys.stderr,
        )
        return 2

    resolved = resolve_provider("telethon")
    api_id_raw = resolved["api_id"].value
    api_hash = resolved["api_hash"].value
    session_name = settings.telethon_session_name or "chief_editor_session"

    if not api_id_raw or not api_hash:
        print(
            "Telethon credentials not in Vault. Add them via:\n"
            '  curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" \\\n'
            '       -H "Content-Type: application/json" \\\n'
            '       http://127.0.0.1:8000/secrets/telethon/api_id \\\n'
            '       -d \'{"value":"<from my.telegram.org>"}\'\n'
            "  …same for api_hash.",
            file=sys.stderr,
        )
        return 3

    try:
        api_id = int(api_id_raw)
    except ValueError:
        print(f"api_id is not a valid integer (got: {api_id_raw!r})", file=sys.stderr)
        return 4

    session_dir = Path("data/telethon").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = session_dir / session_name

    if (session_dir / f"{session_name}.session").exists():
        print(
            f"Session file already exists at {session_path}.session\n"
            f"Delete it manually if you want to re-create."
        )
        return 5

    print(
        f"Creating Telethon session '{session_name}' in {session_dir}\n"
        f"You will be prompted by Telethon for: phone, SMS code, "
        f"optional 2FA password.\n"
        f"None of this is logged by the AI assistant — it goes "
        f"directly into Telethon over the encrypted TG protocol.\n"
    )

    # Telethon's built-in interactive login. It prints/reads using
    # `input()` and `getpass()` directly — we don't intercept.
    client = TelegramClient(str(session_path), api_id, api_hash)
    try:
        client.start()
    except Exception as e:  # noqa: BLE001 — surface concrete error
        print(f"Telethon start failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 6
    finally:
        client.disconnect()

    # Set conservative file permissions where supported (POSIX only;
    # Windows ACLs are managed by user profile).
    try:
        if os.name == "posix":
            os.chmod(f"{session_path}.session", 0o600)
    except OSError:
        pass

    print(f"\nSession file created: {session_path}.session")
    print("This file IS sensitive — protect it like a credential.")
    print(
        "Verify the configuration via the API:\n"
        "  curl -X POST -H \"X-Admin-Token: $ADMIN_TOKEN\" "
        "http://127.0.0.1:8000/readiness/test-telethon"
    )
    return 0


if __name__ == "__main__":
    # Silence getpass's "unused import" warning if telethon import path doesn't use it
    _ = getpass
    sys.exit(main())
