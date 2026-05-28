"""Phase 10 — token cost service.

Computes USD cost from (provider, model, tokens_in, tokens_out). The
underlying price table is kept in code and MUST be reviewed when provider
pricing changes (Anthropic, OpenAI, Ollama Cloud).

Last verified: May 19, 2026.

Conventions:
- Prices are USD per 1M tokens.
- `None` token counts contribute 0 cost (not an error; some providers
  don't report usage, and the mock provider's estimates may be missing).
- Unknown (provider, model) pairs cost 0 and are logged at INFO level so
  operators can spot stale price tables in `/analytics/cost`.
"""
from __future__ import annotations

import logging
from typing import Any, NamedTuple

from sqlmodel import Session, select

from ..models import GenerationRun, GenerationStep

log = logging.getLogger(__name__)


class TokenPrice(NamedTuple):
    """USD per 1M tokens — input and output."""
    input_per_mtok: float
    output_per_mtok: float


# Source: vendor pricing pages, May 19 2026. Update via PR when prices change.
PRICE_TABLE: dict[tuple[str, str], TokenPrice] = {
    # Anthropic — current generation
    ("anthropic", "claude-opus-4-7"): TokenPrice(5.0, 25.0),
    ("anthropic", "claude-opus-4-6"): TokenPrice(5.0, 25.0),
    ("anthropic", "claude-sonnet-4-6"): TokenPrice(3.0, 15.0),
    ("anthropic", "claude-haiku-4-5"): TokenPrice(1.0, 5.0),
    # Anthropic — legacy on the same SKU page (do NOT default to these,
    # they're 3× the price of Opus 4.7)
    ("anthropic", "claude-opus-4-1"): TokenPrice(15.0, 75.0),

    # OpenAI — May 2026 published rates (approximate; verify when wiring)
    ("openai", "gpt-4o"): TokenPrice(2.5, 10.0),
    ("openai", "gpt-4o-mini"): TokenPrice(0.15, 0.6),

    # Ollama Cloud — Kimi tier
    ("ollama", "kimi-k2.6:cloud"): TokenPrice(0.4, 2.0),  # estimate; verify
    ("ollama", "kimi-k2.6"): TokenPrice(0.4, 2.0),

    # Mock — zero cost, used for tests and demo mode
    ("mock", "mock"): TokenPrice(0.0, 0.0),
}


def usd_cost(
    provider: str,
    model: str,
    tokens_in: int | None,
    tokens_out: int | None,
) -> float:
    """USD cost for one call given counters.

    Missing counts contribute 0. Unknown (provider, model) → 0 (logged)."""
    if (tokens_in or 0) == 0 and (tokens_out or 0) == 0:
        return 0.0
    key = (provider or "", model or "")
    price = PRICE_TABLE.get(key)
    if price is None:
        log.info("cost.unknown_price_pair provider=%s model=%s", provider, model)
        return 0.0
    return (
        (tokens_in or 0) * price.input_per_mtok / 1_000_000
        + (tokens_out or 0) * price.output_per_mtok / 1_000_000
    )


class RunCost(NamedTuple):
    run_id: str
    cluster_id: str | None
    status: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    provider: str
    model: str


def cost_per_run(session: Session, run: GenerationRun) -> RunCost:
    """Aggregate token usage and USD cost for one run."""
    rows = list(
        session.exec(
            select(GenerationStep).where(GenerationStep.run_id == run.id)
        ).all()
    )
    tokens_in = sum((s.tokens_in or 0) for s in rows)
    tokens_out = sum((s.tokens_out or 0) for s in rows)
    cost = usd_cost(run.provider, run.model, tokens_in, tokens_out)
    return RunCost(
        run_id=run.id,
        cluster_id=run.cluster_id,
        status=run.status,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost,
        provider=run.provider,
        model=run.model,
    )


def summary(session: Session, limit_runs: int = 200) -> dict[str, Any]:
    """Aggregate cost across the most-recent N runs. Returns:
    {
      "n_runs": int, "tokens_in_total": int, "tokens_out_total": int,
      "cost_usd_total": float, "by_provider": {provider: {...}},
      "by_model": {model: {...}}, "runs": [RunCost as dict...]
    }
    """
    rows = list(
        session.exec(
            select(GenerationRun)
            .order_by(GenerationRun.created_at.desc())
            .limit(max(1, min(int(limit_runs), 2000)))
        ).all()
    )
    runs = [cost_per_run(session, r) for r in rows]
    by_provider: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    for r in runs:
        for bucket, key in ((by_provider, r.provider or "unknown"),
                            (by_model, r.model or "unknown")):
            slot = bucket.setdefault(key, {
                "n_runs": 0,
                "tokens_in_total": 0,
                "tokens_out_total": 0,
                "cost_usd_total": 0.0,
            })
            slot["n_runs"] += 1
            slot["tokens_in_total"] += r.tokens_in
            slot["tokens_out_total"] += r.tokens_out
            slot["cost_usd_total"] += r.cost_usd
    return {
        "n_runs": len(runs),
        "tokens_in_total": sum(r.tokens_in for r in runs),
        "tokens_out_total": sum(r.tokens_out for r in runs),
        "cost_usd_total": sum(r.cost_usd for r in runs),
        "by_provider": by_provider,
        "by_model": by_model,
        "runs": [r._asdict() for r in runs],
    }


__all__ = ["PRICE_TABLE", "RunCost", "TokenPrice", "cost_per_run", "summary", "usd_cost"]
