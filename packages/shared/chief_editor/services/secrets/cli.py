"""Vault CLI helpers.

Usage:
    python -m chief_editor.services.secrets generate-key
    python -m chief_editor.services.secrets rotate-key
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlmodel import select

from ...db import session_scope
from ...models import IntegrationSecret
from .crypto import KeyRotationError, generate_key, rotate_token

log = logging.getLogger("chief_editor.secrets.cli")


def cmd_generate_key(_: argparse.Namespace) -> int:
    print(generate_key())  # noqa: T201 — intended CLI output
    return 0


def cmd_rotate_key(_: argparse.Namespace) -> int:
    """Re-encrypt every stored secret with the current MASTER_ENCRYPTION_KEY.

    Set the new key as `MASTER_ENCRYPTION_KEY` and put the OLD value into
    `MASTER_ENCRYPTION_KEYS_LEGACY` BEFORE running this. MultiFernet reads
    both, rewrites with the primary, and after this completes you can drop
    the legacy entry.
    """
    rewritten = 0
    failed: list[str] = []
    with session_scope() as session:
        rows = list(session.exec(select(IntegrationSecret)).all())
        for row in rows:
            try:
                row.encrypted_value = rotate_token(row.encrypted_value)
                session.add(row)
                rewritten += 1
            except KeyRotationError:
                failed.append(f"{row.provider}/{row.key_name}")
        session.commit()
    print(f"rotated={rewritten} failed={len(failed)}")  # noqa: T201
    for ref in failed:
        print(f"  ! {ref}", file=sys.stderr)  # noqa: T201
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chief_editor.services.secrets")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate-key", help="Print a fresh MASTER_ENCRYPTION_KEY")
    sub.add_parser(
        "rotate-key",
        help="Re-encrypt every IntegrationSecret row with the current primary key",
    )
    args = parser.parse_args(argv)
    if args.cmd == "generate-key":
        return cmd_generate_key(args)
    if args.cmd == "rotate-key":
        return cmd_rotate_key(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
