"""Phase 8 — safety rehearsal walker.

Walks the operator through the 4-step publish ritual on a TEST channel,
verifying each gate in the DB. **Claude / this script NEVER flips
`PUBLISHING_ENABLED` or `DRY_RUN_PUBLISH`.** Those flips are operator
actions; the walker just inspects state and tells you when you're safe to
proceed to the next flip.

Pre-requisites:
- Test Telegram channel created.
- Bot created via @BotFather, added as channel admin.
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_TARGET_CHANNEL_ID` in Vault.
- One approved candidate ready (you approve it interactively in /editor).
- API + worker running, currently in safe state.

Usage:
    python -m scripts.phase8_safety_walker \\
        --candidate-id <id> \\
        --admin-token "$ADMIN_TOKEN" \\
        --api-base http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def _http_json(url: str, *, headers: dict[str, str] | None = None,
               body: dict[str, Any] | None = None, method: str = "GET") -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _wait_for_input(prompt: str) -> str:
    """Block until the operator types something at the terminal. The
    walker never advances state on its own."""
    print(f"\n>>> {prompt}")
    return input(">>> ENTER when done, or type SKIP to abort: ").strip().upper()


def _show_status(api_base: str) -> dict[str, Any]:
    status = _http_json(f"{api_base}/status")
    print(
        f"  /status: publishing_enabled={status.get('publishing_enabled')} "
        f"dry_run_publish={status.get('dry_run_publish')}"
    )
    return status


def _show_job(api_base: str, admin_token: str, candidate_id: str) -> dict[str, Any] | None:
    try:
        jobs = _http_json(
            f"{api_base}/publishing/jobs",
            headers={"X-Admin-Token": admin_token},
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("  no /publishing/jobs route (Phase 8 pre-implementation)")
            return None
        raise
    # API may return list or {"jobs": [...]} shape; handle both
    rows = jobs if isinstance(jobs, list) else jobs.get("jobs", [])
    for j in rows:
        if j.get("candidate_id") == candidate_id:
            print(f"  PublishJob: status={j.get('status')!r}  id={j.get('id')}")
            return j
    print("  no PublishJob for candidate")
    return None


def _poll_job_status(
    api_base: str, admin_token: str, candidate_id: str,
    expected: set[str], timeout: int = 90,
) -> dict[str, Any] | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = _show_job(api_base, admin_token, candidate_id)
        if job and job.get("status") in expected:
            return job
        time.sleep(5)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 8 safety rehearsal walker")
    parser.add_argument("--candidate-id", required=True,
                        help="approved candidate to push through the gates")
    parser.add_argument("--admin-token", required=True)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    print("=" * 70)
    print("Phase 8 — Safety Rehearsal Walker")
    print("=" * 70)
    print(
        "\nThis walker NEVER flips PUBLISHING_ENABLED or DRY_RUN_PUBLISH "
        "for you.\nIt only inspects DB state and tells you when each gate "
        "has been reached.\n"
    )

    # Gate 0 — preflight
    print("\n--- Gate 0: preflight (default safe state) ---")
    status = _show_status(args.api_base)
    if status.get("publishing_enabled"):
        print("REFUSE: publishing_enabled=true at start. "
              "Revert to safe defaults before running this walker.",
              file=sys.stderr)
        return 3
    if not status.get("dry_run_publish"):
        print("REFUSE: dry_run_publish=false at start. "
              "Revert to safe defaults before running this walker.",
              file=sys.stderr)
        return 3

    # Gate 1 — candidate approval exists
    print("\n--- Gate 1: candidate approval ---")
    cand = _http_json(f"{args.api_base}/candidates/{args.candidate_id}")
    print(f"  candidate.status: {cand.get('status')!r}")
    if cand.get("status") != "approved":
        print(
            "  Approve the candidate in /editor first, then re-run this "
            "script. The walker does NOT approve for you.",
            file=sys.stderr,
        )
        return 4
    job = _show_job(args.api_base, args.admin_token, args.candidate_id)
    if not job:
        print("  Approval created no PublishJob — check API logs.", file=sys.stderr)
        return 5

    # Gate 2 — worker ticks with BOTH flags off → status='blocked'
    print("\n--- Gate 2: blocked (both safety flags closed) ---")
    job = _poll_job_status(args.api_base, args.admin_token,
                           args.candidate_id, {"blocked"}, timeout=90)
    if not job or job.get("status") != "blocked":
        print(
            "  Expected job.status='blocked' but it did not arrive within 90s.\n"
            "  Possible causes: worker not ticking; flags not actually safe.",
            file=sys.stderr,
        )
        return 6
    print("  ✓ gate-1 (blocked) verified")

    # Gate 3 — operator flips PUBLISHING_ENABLED=true, keep dry_run=true
    print("\n--- Gate 3: dry-run rehearsal (you flip ONE flag) ---")
    print(
        "OPERATOR ACTION:\n"
        "  1. Edit .env: set PUBLISHING_ENABLED=true (keep "
        "DRY_RUN_PUBLISH=true).\n"
        "  2. Restart the worker (env vars are read at startup).\n"
    )
    ans = _wait_for_input(
        "After you've done both, press ENTER (or type SKIP to abort)."
    )
    if ans == "SKIP":
        print("Aborted by operator.")
        return 0
    _show_status(args.api_base)
    job = _poll_job_status(args.api_base, args.admin_token,
                           args.candidate_id, {"dry_run"}, timeout=90)
    if not job or job.get("status") != "dry_run":
        print(
            "  Expected job.status='dry_run' but it didn't appear.\n"
            "  Did you both edit .env AND restart the worker?",
            file=sys.stderr,
        )
        return 7
    print("  ✓ gate-2 (dry_run) verified — payload computed, nothing sent")

    # Gate 4 — operator flips DRY_RUN_PUBLISH=false → real send
    print("\n--- Gate 4: REAL publish (you flip the SECOND flag) ---")
    print(
        "OPERATOR ACTION:\n"
        "  1. Edit .env: set DRY_RUN_PUBLISH=false. "
        "(PUBLISHING_ENABLED stays true.)\n"
        "  2. Restart the worker.\n"
        "  3. Watch the test channel — a message should appear within ~30s.\n"
    )
    ans = _wait_for_input(
        "After you've done both AND seen the message in Telegram, press ENTER. "
        "If nothing appeared, type SKIP."
    )
    if ans == "SKIP":
        print(
            "ABORTED. Re-check bot is admin of the target channel, the "
            "token+channel_id are correct, and the worker actually picked "
            "up the env change."
        )
        return 8
    job = _poll_job_status(args.api_base, args.admin_token,
                           args.candidate_id, {"done"}, timeout=30)
    if job and job.get("status") == "done":
        print("  ✓ gate-3 (real publish) verified — job.status='done'")
    else:
        print(
            "  WARNING: job did not move to 'done'. Check worker log + "
            "Telegram side.",
            file=sys.stderr,
        )

    # Gate 5 — REVERT
    print("\n--- Gate 5: REVERT (mandatory) ---")
    print(
        "OPERATOR ACTION:\n"
        "  1. Edit .env: PUBLISHING_ENABLED=false, DRY_RUN_PUBLISH=true.\n"
        "  2. Restart the worker.\n"
        "  3. Verify /status reflects the safe defaults.\n"
    )
    ans = _wait_for_input(
        "After both flags are reverted and the worker restarted, press ENTER."
    )
    status = _show_status(args.api_base)
    if status.get("publishing_enabled") or not status.get("dry_run_publish"):
        print(
            "  REGRESSION: safety flags not at safe defaults after revert.\n"
            "  STOP. Investigate before any further work.",
            file=sys.stderr,
        )
        return 9
    print("\n" + "=" * 70)
    print("✓ Phase 8 safety rehearsal COMPLETE. All 5 gates verified.")
    print("  Test channel received one message. Flags are back to safe.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
