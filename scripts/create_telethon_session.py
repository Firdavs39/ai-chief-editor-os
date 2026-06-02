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
        f"Phone, code and optional 2FA password go directly into Telethon\n"
        f"over the encrypted TG protocol — the AI assistant does not see them.\n"
    )

    # Explicit login flow so we can tell the user HOW Telegram delivered the
    # code (app / sms / call / missed-call). The high-level client.start()
    # hides this, which makes "the code never arrived" impossible to debug.
    # Telethon methods are coroutines — we drive them on the client's own
    # event loop. input()/getpass() block that loop, which is fine for a CLI.
    from telethon.errors import (  # type: ignore
        PhoneCodeInvalidError,
        SessionPasswordNeededError,
    )

    _DELIVERY = {
        "SentCodeTypeApp": (
            "IN THE TELEGRAM APP — open Telegram, look for a message from "
            "the 'Telegram' service chat (blue checkmark) at the top."
        ),
        "SentCodeTypeSms": "by SMS to your phone.",
        "SentCodeTypeCall": (
            "by a PHONE CALL — answer it, an automated voice reads the digits."
        ),
        "SentCodeTypeFlashCall": (
            "by a FLASH CALL — the code is part of the incoming call's number."
        ),
        "SentCodeTypeMissedCall": (
            "by a MISSED CALL — Telegram calls and hangs up; the CODE is the "
            "LAST DIGITS of the phone number that called you. Check your call log."
        ),
    }

    client = TelegramClient(str(session_path), api_id, api_hash)

    async def _login() -> int:
        await client.connect()
        try:
            phone = input("Phone (with country code, e.g. +99890XXXXXXX): ").strip()
            sent = await client.send_code_request(phone)

            type_name = type(sent.type).__name__
            human = _DELIVERY.get(type_name, f"via {type_name}.")
            print(f"\n>>> Telegram sent the code {human}")
            nxt = getattr(sent, "next_type", None)
            if nxt is not None:
                print(
                    f">>> If nothing arrives in ~60s, Telegram will retry via "
                    f"{type(nxt).__name__}. Keep this window open and wait."
                )
            print()

            code = input("Enter the code: ").strip()
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                print("\nThis account has 2FA enabled.")
                pw = getpass.getpass("Enter your Telegram 2FA password: ")
                await client.sign_in(password=pw)
            except PhoneCodeInvalidError:
                print(
                    "Code rejected as invalid. Re-run the script and try again "
                    "(make sure you typed the exact digits).",
                    file=sys.stderr,
                )
                return 7
            return 0
        finally:
            await client.disconnect()

    try:
        rc = client.loop.run_until_complete(_login())
    except Exception as e:  # noqa: BLE001 — surface concrete error
        print(f"Telethon login failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 6
    if rc != 0:
        return rc

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
