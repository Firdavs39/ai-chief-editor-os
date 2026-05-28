"""Phase 6 — reproducibility batch.

Enqueues N runs on N distinct clusters back-to-back, polls each to terminal,
writes a CSV report with per-run outcome and step durations. Read-only
against an already-running API + worker; this script does NOT execute any
LLM call itself.

Usage:
    python scripts/phase6_batch.py --n 8 --budget-seconds 18000 \\
        --admin-token "$ADMIN_TOKEN" \\
        --api-base http://127.0.0.1:8000 \\
        --out reports/phase6_batch.csv

Operator gates:
- This script ASSUMES the running API has `publishing_enabled=false` and
  `dry_run_publish=true`. It will refuse to start otherwise.
- It will NOT approve, publish, or contact any external service. It
  enqueues runs and reads back their outcomes.

Exit codes:
- 0 — every run terminal within budget.
- 2 — budget exhausted with one or more runs still non-terminal.
- 3 — pre-flight safety check failed (publishing not safe-by-default).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

TERMINAL = {"succeeded", "failed", "cancelled"}


def _http_json(url: str, *, headers: dict[str, str] | None = None,
               body: dict[str, Any] | None = None, method: str = "GET") -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _safe_preflight(api_base: str) -> dict[str, Any]:
    """Refuse to launch the batch if the API is not in safe-default state."""
    status = _http_json(f"{api_base}/status")
    if status.get("publishing_enabled"):
        print(
            "REFUSE: /status reports publishing_enabled=true. "
            "Set PUBLISHING_ENABLED=false before running this batch.",
            file=sys.stderr,
        )
        sys.exit(3)
    if not status.get("dry_run_publish"):
        print(
            "REFUSE: /status reports dry_run_publish=false. "
            "Set DRY_RUN_PUBLISH=true before running this batch.",
            file=sys.stderr,
        )
        sys.exit(3)
    return status


def _list_clusters(api_base: str, want: int) -> list[dict[str, Any]]:
    """Return up to `want` distinct clusters sorted by score, regardless
    of prior runs. We don't avoid clusters that already have candidates —
    Phase 6's goal is reproducibility against THE WORKFLOW, not novelty."""
    rows = _http_json(f"{api_base}/trends")
    return rows[:want]


def _enqueue(api_base: str, admin_token: str, cluster_id: str) -> str:
    body = {"cluster_id": cluster_id, "top_n": 1, "requested_by": "phase6"}
    resp = _http_json(
        f"{api_base}/generation-runs",
        headers={"X-Admin-Token": admin_token},
        body=body,
        method="POST",
    )
    runs = resp.get("runs") or []
    if not runs:
        raise RuntimeError(f"enqueue returned no run for cluster {cluster_id}")
    return runs[0]["id"]


def _poll_until_terminal(
    api_base: str,
    admin_token: str,
    run_id: str,
    deadline: float,
    interval: int = 30,
) -> dict[str, Any]:
    while True:
        if time.time() > deadline:
            return {"status": "budget_exceeded", "run_id": run_id}
        try:
            run = _http_json(
                f"{api_base}/generation-runs/{run_id}",
                headers={"X-Admin-Token": admin_token},
            )
        except urllib.error.URLError as e:
            print(f"[{run_id}] poll error: {e}", file=sys.stderr)
            time.sleep(interval)
            continue
        if run["status"] in TERMINAL:
            return run
        time.sleep(interval)


def _fetch_steps(api_base: str, admin_token: str, run_id: str) -> list[dict[str, Any]]:
    return _http_json(
        f"{api_base}/generation-runs/{run_id}/steps",
        headers={"X-Admin-Token": admin_token},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 reproducibility batch")
    parser.add_argument("--n", type=int, default=8, help="number of clusters")
    parser.add_argument("--budget-seconds", type=int, default=18000,
                        help="total wall budget (5h default)")
    parser.add_argument("--admin-token", required=True)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="reports/phase6_batch.csv")
    parser.add_argument("--poll-interval", type=int, default=30)
    args = parser.parse_args()

    print(f"phase6: preflight on {args.api_base}", flush=True)
    status = _safe_preflight(args.api_base)
    print(f"phase6: safe ({status['llm_provider']}, dry_run={status['dry_run_publish']}, "
          f"publishing_enabled={status['publishing_enabled']})", flush=True)

    clusters = _list_clusters(args.api_base, args.n)
    if len(clusters) < args.n:
        print(
            f"WARNING: only {len(clusters)} clusters available, want {args.n}",
            file=sys.stderr,
        )

    started = time.time()
    deadline = started + args.budget_seconds

    results: list[dict[str, Any]] = []
    for i, cluster in enumerate(clusters):
        if time.time() > deadline:
            print("budget exhausted before launching remaining runs", file=sys.stderr)
            break

        cluster_id = cluster["id"]
        cluster_text = (cluster.get("representative_text") or "")[:60]
        print(f"\n[{i+1}/{len(clusters)}] cluster={cluster_id[:8]}... text={cluster_text!r}",
              flush=True)

        try:
            run_id = _enqueue(args.api_base, args.admin_token, cluster_id)
        except Exception as e:
            print(f"  enqueue failed: {e}", file=sys.stderr)
            results.append({
                "i": i + 1, "cluster_id": cluster_id, "run_id": "", "status": "enqueue_failed",
                "step_reached": 0, "duration_sec": 0, "error_class": type(e).__name__,
                "error_message": str(e)[:200], "candidate_id": "", "used_fallback": "",
                "tokens_in_total": 0, "tokens_out_total": 0,
            })
            continue

        print(f"  run_id={run_id} polling...", flush=True)
        t0 = time.time()
        terminal = _poll_until_terminal(args.api_base, args.admin_token, run_id,
                                        deadline, interval=args.poll_interval)
        dur = int(time.time() - t0)

        steps = _fetch_steps(args.api_base, args.admin_token, run_id)
        tokens_in = sum((s.get("tokens_in") or 0) for s in steps)
        tokens_out = sum((s.get("tokens_out") or 0) for s in steps)
        step_reached = max((s["step_index"] for s in steps), default=-1) + 1

        results.append({
            "i": i + 1,
            "cluster_id": cluster_id,
            "run_id": run_id,
            "status": terminal.get("status"),
            "step_reached": step_reached,
            "duration_sec": dur,
            "error_class": terminal.get("error_class", ""),
            "error_message": (terminal.get("error_message") or "")[:200],
            "candidate_id": terminal.get("candidate_id") or "",
            "used_fallback": "",  # would require parsing logs; skipped for v1
            "tokens_in_total": tokens_in,
            "tokens_out_total": tokens_out,
        })
        print(f"  → {terminal.get('status')} in {dur}s, "
              f"tokens={tokens_in}/{tokens_out}", flush=True)

    # Write CSV
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    fieldnames = list(results[0].keys()) if results else [
        "i", "cluster_id", "run_id", "status", "step_reached",
        "duration_sec", "error_class", "error_message",
        "candidate_id", "used_fallback", "tokens_in_total", "tokens_out_total",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    succeeded = sum(1 for r in results if r["status"] == "succeeded")
    failed = sum(1 for r in results if r["status"] == "failed")
    other = len(results) - succeeded - failed
    total_in = sum(r["tokens_in_total"] for r in results)
    total_out = sum(r["tokens_out_total"] for r in results)
    print(f"\nphase6 batch complete in {int(time.time() - started)}s")
    print(f"  succeeded={succeeded} failed={failed} other={other}")
    print(f"  total tokens: in={total_in} out={total_out}")
    print(f"  CSV: {args.out}")

    if other > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
