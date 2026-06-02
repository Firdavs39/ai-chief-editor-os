"""Telethon QR login — no SMS / no typed code.

Telegram (2026) made SMS/call login codes unreliable for third-party
MTProto clients. QR login sidesteps the whole problem: you scan a code
inside the official Telegram app and the session authorizes directly —
nothing to type.

Pre-requisites:
1. api_id + api_hash registered at https://my.telegram.org.
2. Those values POSTed to /secrets/telethon in the running API (vault).
3. The official Telegram app on your phone, logged in.

Usage:
    python scripts/telethon_qr_login.py

A QR image opens automatically (and an ASCII QR prints as backup). In
Telegram:  Settings -> Devices -> Link Desktop Device -> scan it.

If you have 2FA enabled, you'll be asked for the cloud password locally
(getpass) — the AI assistant never sees it.
"""
from __future__ import annotations

import asyncio
import contextlib
import getpass
import os
import sys
from pathlib import Path

# Make block-character output survive the Windows console (cp1251 by default).
with contextlib.suppress(Exception):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
if os.name == "nt":
    os.system("chcp 65001 >nul 2>&1")

try:
    from chief_editor.services.integration_config import resolve_provider
    from chief_editor.settings import get_settings
except ImportError:
    print(
        "Could not import chief_editor — set PYTHONPATH first:\n"
        '  $env:PYTHONPATH = "packages/shared;apps/api;apps/worker"',
        file=sys.stderr,
    )
    raise

_QR_PNG = Path("data/telethon/login_qr.png").resolve()


def _save_qr_png(url: str) -> Path:
    import qrcode

    img = qrcode.make(url)
    _QR_PNG.parent.mkdir(parents=True, exist_ok=True)
    img.save(_QR_PNG)
    return _QR_PNG


def _print_qr_ascii(url: str) -> None:
    """Best-effort ASCII QR. Never fatal — PNG is the reliable channel."""
    try:
        import qrcode

        qr = qrcode.QRCode(border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        pass


def _open_file(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}" >/dev/null 2>&1')
    except Exception:
        pass


def main() -> int:
    try:
        from telethon import TelegramClient  # type: ignore
        from telethon.errors import SessionPasswordNeededError  # type: ignore
    except ImportError:
        print("telethon not installed: pip install telethon", file=sys.stderr)
        return 1

    settings = get_settings()
    if not settings.vault_enabled:
        print(
            "Vault disabled (MASTER_ENCRYPTION_KEY missing) — cannot read creds.",
            file=sys.stderr,
        )
        return 2

    resolved = resolve_provider("telethon")
    api_id_raw = resolved["api_id"].value
    api_hash = resolved["api_hash"].value
    if not (api_id_raw and api_hash):
        print("Telethon api_id/api_hash not in vault. Add them first.", file=sys.stderr)
        return 3
    try:
        api_id = int(api_id_raw)
    except ValueError:
        print(f"api_id not an integer: {api_id_raw!r}", file=sys.stderr)
        return 4

    session_name = settings.telethon_session_name or "chief_editor_session"
    session_dir = Path("data/telethon").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path = str(session_dir / session_name)

    client = TelegramClient(session_path, api_id, api_hash)

    async def _qr_login() -> int:
        await client.connect()
        try:
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"Already authorized as {me.first_name}. Nothing to do.")
                return 0

            qr = await client.qr_login()
            png = _save_qr_png(qr.url)
            _open_file(png)
            print("\n=========================================================")
            print(" SCAN THE QR THAT JUST OPENED (image window)")
            print(f"   file: {png}")
            print(" In Telegram: Settings -> Devices -> Link Desktop Device")
            print("=========================================================\n")
            print("(ASCII backup below — ignore if the image opened)\n")
            _print_qr_ascii(qr.url)

            attempts = 0
            while True:
                print("\nWaiting for scan... (refreshes every 50s, Ctrl+C to abort)")
                try:
                    await qr.wait(timeout=50)
                    break  # scanned + authorized
                except asyncio.TimeoutError:
                    attempts += 1
                    if attempts >= 6:
                        print("Gave up after ~5 min without a scan.", file=sys.stderr)
                        return 7
                    await qr.recreate()
                    png = _save_qr_png(qr.url)
                    _open_file(png)
                    print("\n--- QR refreshed (new image opened) ---\n")
                    _print_qr_ascii(qr.url)
                    continue
                except SessionPasswordNeededError:
                    print("\nThis account has 2FA enabled.")
                    pw = getpass.getpass("Enter your Telegram cloud password: ")
                    await client.sign_in(password=pw)
                    break

            me = await client.get_me()
            uname = f"@{me.username}" if me.username else "(no username)"
            print(f"\nLogged in as {me.first_name} {uname}.")
            return 0
        finally:
            await client.disconnect()

    try:
        rc = client.loop.run_until_complete(_qr_login())
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        return 130
    except Exception as e:  # noqa: BLE001 — surface concrete error
        print(f"QR login failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 6

    # Clean up the QR image — it is single-use and no longer needed.
    with contextlib.suppress(OSError):
        _QR_PNG.unlink(missing_ok=True)

    if rc == 0:
        print(f"\nSession file: {session_path}.session")
        print("This file IS sensitive — protect it like a credential.")
        print("The worker will start reading your channels within ~5 minutes.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
