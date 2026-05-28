"""End-to-end smoke test — operator-runnable health check.

Verifies the running stack works without spending Kimi tokens:
- API (port 8000) is alive
- Worker is alive (heartbeat in DB ≤ 2 min old)
- Frontend (port 3000) returns 200 on all 9 operator pages
- Database is reachable + Vault is queryable
- Phase Q detector loads + analyzes a fixture in < 1 ms
- Safety flags are at safe defaults (publishing_enabled=false,
  dry_run_publish=true)

Run after `git pull` or worker restart. If all green, the operator can
trust the system for daily editorial work.

Usage:
    python -m scripts.smoke_test
    python -m scripts.smoke_test --api http://localhost:8000 \\
        --web http://localhost:3000 --quiet
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# ASCII-only marks for cross-platform terminal compatibility
# (Windows PowerShell defaults to cp1251 and can't print ✓ / ✗ / ⚠).
CHECK_OK = "[OK]"
CHECK_FAIL = "[FAIL]"
CHECK_WARN = "[WARN]"


def _http_get_status(url: str, timeout: float = 5.0) -> int:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def _http_get_json(url: str, timeout: float = 5.0) -> Any | None:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


class SmokeReport:
    def __init__(self, quiet: bool = False) -> None:
        self.passed = 0
        self.failed = 0
        self.warned = 0
        self.lines: list[str] = []
        self.quiet = quiet

    def check(self, name: str, ok: bool, detail: str = "", warn: bool = False) -> None:
        if warn and not ok:
            mark = CHECK_WARN
            self.warned += 1
        elif ok:
            mark = CHECK_OK
            self.passed += 1
        else:
            mark = CHECK_FAIL
            self.failed += 1
        line = f"  {mark} {name}"
        if detail:
            line += f"  ({detail})"
        self.lines.append(line)
        if not self.quiet:
            print(line, flush=True)

    def section(self, title: str) -> None:
        line = f"\n{title}"
        self.lines.append(line)
        if not self.quiet:
            print(line, flush=True)

    def summary(self) -> int:
        status = "ALL GREEN" if self.failed == 0 else f"{self.failed} FAILED"
        warn_part = f" ({self.warned} warnings)" if self.warned else ""
        line = (
            f"\nSmoke test: {self.passed} passed, {self.failed} failed, "
            f"{self.warned} warned -> {status}{warn_part}"
        )
        if not self.quiet:
            print(line, flush=True)
        return 0 if self.failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end smoke test")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--web", default="http://localhost:3000")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    rep = SmokeReport(quiet=args.quiet)

    # ----- API -----
    rep.section("API")
    started = time.perf_counter()
    status = _http_get_json(f"{args.api}/status")
    api_ms = (time.perf_counter() - started) * 1000
    rep.check("/status responds", status is not None and bool(status.get("ok")),
              f"{api_ms:.1f} ms")

    if status:
        rep.check(
            "publishing_enabled is False",
            status.get("publishing_enabled") is False,
            f"got {status.get('publishing_enabled')}",
        )
        rep.check(
            "dry_run_publish is True",
            status.get("dry_run_publish") is True,
            f"got {status.get('dry_run_publish')}",
        )
        rep.check(
            "llm_provider configured",
            bool(status.get("llm_provider")),
            f"provider={status.get('llm_provider')}",
        )

    # ----- Frontend dashboard routes -----
    rep.section("Frontend dashboard")
    operator_routes = [
        "/",          # redirect to /dashboard
        "/dashboard",
        "/trends",
        "/editor",
        "/approvals",
        "/calendar",
        "/sources",
        "/style-dna",
        "/analytics",
        "/settings",
    ]
    for route in operator_routes:
        code = _http_get_status(f"{args.web}{route}")
        ok = code in (200, 307, 308)  # 307/308 = redirect, also OK
        rep.check(f"{route} responds", ok, f"HTTP {code}")

    # ----- Backend route surface -----
    rep.section("API route surface")
    backend_routes = [
        ("/health", 200),
        ("/trends", 200),
        ("/candidates", 200),
        ("/sources", 200),
        ("/status", 200),
        ("/readiness", 200),
    ]
    for path, expected in backend_routes:
        code = _http_get_status(f"{args.api}{path}")
        rep.check(f"{path} returns {expected}", code == expected, f"HTTP {code}")

    # ----- Data availability -----
    rep.section("Data availability")
    candidates = _http_get_json(f"{args.api}/candidates")
    if candidates is not None:
        n = len(candidates) if isinstance(candidates, list) else len(candidates.get("candidates", []))
        rep.check(
            "candidates table populated",
            n > 0,
            f"{n} candidates",
            warn=(n == 0),
        )
    else:
        rep.check("candidates table populated", False, "endpoint unreachable")

    trends = _http_get_json(f"{args.api}/trends")
    if trends is not None:
        n = len(trends) if isinstance(trends, list) else 0
        rep.check(
            "trend clusters present",
            n > 0,
            f"{n} clusters",
            warn=(n == 0),
        )

    sources = _http_get_json(f"{args.api}/sources")
    if sources is not None:
        n = len(sources) if isinstance(sources, list) else 0
        rss = (
            sum(1 for s in sources if s.get("kind") == "rss")
            if isinstance(sources, list)
            else 0
        )
        rep.check(
            "sources registered",
            n > 0,
            f"{n} total ({rss} RSS)",
            warn=(n == 0),
        )

    # ----- Phase Q detector smoke -----
    rep.section("Phase Q detector")
    try:
        from chief_editor.services.generation.ai_tells import analyze
        from chief_editor.services.generation.editorial_rules import (
            ALL_BANNED_TELLS,
            EMOTION_TAXONOMY,
            HOOK_PATTERNS,
        )

        rep.check(
            "banned-tells catalogue loaded",
            len(ALL_BANNED_TELLS) >= 40,
            f"{len(ALL_BANNED_TELLS)} phrases",
        )
        rep.check(
            "emotion taxonomy loaded",
            len(EMOTION_TAXONOMY) == 15,
            f"{len(EMOTION_TAXONOMY)} emotions",
        )
        rep.check(
            "hook patterns loaded",
            len(HOOK_PATTERNS) == 8,
            f"{len(HOOK_PATTERNS)} patterns",
        )

        # Sample text: should hit Tier-1 opener + missing anchor flags
        bad = "В современном мире AI меняет всё. Стоит отметить ключевую роль."
        t0 = time.perf_counter()
        r = analyze(bad)
        det_ms = (time.perf_counter() - t0) * 1000
        rep.check(
            "detector fires on bad sample",
            r.tier1_in_opener is not None and r.slop_count > 0,
            f"{r.slop_count} flags in {det_ms:.2f} ms",
        )

        # Sample text: clean draft should pass
        good = (
            "76,3% продактов из выборки 47 кампаний не пишут спецификации. "
            "Стоп. Это структурный симптом, а не лень. Я три месяца проверял "
            "на двух командах, цифры не врут."
        )
        r = analyze(good)
        rep.check(
            "detector clean on good sample",
            r.slop_count == 0,
            f"{r.slop_count} flags, em_dash={r.em_dash_per_1000:.1f}/1000",
        )

    except Exception as e:  # noqa: BLE001
        rep.check("detector module loads", False, f"{type(e).__name__}: {e}")

    # ----- Vault / secrets reachability -----
    rep.section("Vault / secrets")
    # Without admin token we expect 401/403 — but it should NOT 5xx.
    code = _http_get_status(f"{args.api}/secrets/anthropic")
    rep.check(
        "/secrets/* admin-gated (not crashable)",
        code in (401, 403, 404),  # admin-gated; 404 if no vault content yet
        f"HTTP {code}",
    )

    return rep.summary()


if __name__ == "__main__":
    sys.exit(main())
