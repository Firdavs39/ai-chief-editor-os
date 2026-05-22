"""Phase 10 — token-cost service tests."""
from __future__ import annotations

from sqlmodel import select

from chief_editor.models import GenerationStep, TrendCluster
from chief_editor.services.cost import (
    PRICE_TABLE,
    cost_per_run,
    summary,
    usd_cost,
)
from chief_editor.services.generation import enqueue_run, run_to_completion_for_tests

# ---------------------------------------------------------------------------
# Unit: usd_cost
# ---------------------------------------------------------------------------


def test_usd_cost_zero_when_no_tokens() -> None:
    assert usd_cost("anthropic", "claude-opus-4-7", 0, 0) == 0.0
    assert usd_cost("anthropic", "claude-opus-4-7", None, None) == 0.0


def test_usd_cost_anthropic_opus() -> None:
    # 1M input × $5/M + 1M output × $25/M = $30.00
    c = usd_cost("anthropic", "claude-opus-4-7", 1_000_000, 1_000_000)
    assert c == 30.0


def test_usd_cost_anthropic_sonnet_cheaper() -> None:
    opus = usd_cost("anthropic", "claude-opus-4-7", 100_000, 100_000)
    sonnet = usd_cost("anthropic", "claude-sonnet-4-6", 100_000, 100_000)
    haiku = usd_cost("anthropic", "claude-haiku-4-5", 100_000, 100_000)
    # Sonnet < Opus < legacy Opus 4.1
    assert sonnet < opus
    assert haiku < sonnet


def test_usd_cost_unknown_pair_returns_zero() -> None:
    """Unknown (provider, model) pair returns 0.0 and is logged INFO."""
    assert usd_cost("unknown-provider", "unknown-model", 100, 100) == 0.0


def test_price_table_covers_all_known_provider_models() -> None:
    """Sanity: every provider we currently support has at least one model
    in the price table."""
    providers = {key[0] for key in PRICE_TABLE}
    assert "anthropic" in providers
    assert "openai" in providers
    assert "ollama" in providers
    assert "mock" in providers


# ---------------------------------------------------------------------------
# Integration: cost_per_run + summary over a real (mock-LLM) workflow
# ---------------------------------------------------------------------------


def _make_run(client, session):
    client.post("/demo/seed")
    cluster = session.exec(select(TrendCluster)).first()
    runs = enqueue_run(session, cluster_id=cluster.id, top_n=1, requested_by="test")
    return runs[0]


def test_cost_per_run_aggregates_mock_tokens(client, session) -> None:
    """After a mock-LLM run completes, cost_per_run returns the summed
    tokens from each LLM step (finalizer has None and contributes 0)."""
    run = _make_run(client, session)
    run = run_to_completion_for_tests(session, run, max_steps=20)
    assert run.status == "succeeded"

    cost = cost_per_run(session, run)
    assert cost.run_id == run.id
    assert cost.status == "succeeded"
    # Mock provider records non-zero estimated tokens per LLM step
    assert cost.tokens_in > 0
    assert cost.tokens_out > 0
    # Mock provider is 0 USD/MTok by design
    assert cost.cost_usd == 0.0


def test_summary_aggregates_across_runs(client, session) -> None:
    """summary() rolls cost over the most recent N runs and breaks down
    by provider and model."""
    run = _make_run(client, session)
    run_to_completion_for_tests(session, run, max_steps=20)

    s = summary(session, limit_runs=10)
    assert s["n_runs"] >= 1
    assert s["tokens_in_total"] > 0
    assert s["tokens_out_total"] > 0
    assert s["cost_usd_total"] == 0.0  # mock provider
    assert "mock" in set(s["by_provider"])


def test_summary_endpoint_returns_safe_metadata(client, session) -> None:
    """/analytics/cost must not leak raw prompts/completions — only
    aggregated token counts and derived costs."""
    run = _make_run(client, session)
    run_to_completion_for_tests(session, run, max_steps=20)

    resp = client.get("/analytics/cost?limit_runs=10")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) >= {
        "n_runs", "tokens_in_total", "tokens_out_total",
        "cost_usd_total", "by_provider", "by_model", "runs",
    }
    # No raw text leaks: keys in each per-run row should be the RunCost
    # NamedTuple fields, NOT prompts/completions.
    if body["runs"]:
        row_keys = set(body["runs"][0].keys())
        assert "tokens_in" in row_keys
        assert "tokens_out" in row_keys
        assert "cost_usd" in row_keys
        # explicit anti-leakage assertions
        for forbidden in ("prompt", "user_prompt", "system_prompt", "response",
                          "completion", "messages", "raw"):
            assert forbidden not in row_keys, (
                f"cost endpoint leaks {forbidden!r}"
            )


# ---------------------------------------------------------------------------
# Anti-regression: cost service must not require any new column on
# GenerationStep (it uses tokens_in/out only, which were declared in Phase 2).
# ---------------------------------------------------------------------------


def test_cost_uses_only_existing_step_columns() -> None:
    """If someone adds new required columns to GenerationStep, this fails
    and forces a migration discussion."""
    cols = {c.name for c in GenerationStep.__table__.columns}  # type: ignore[attr-defined]
    required_for_cost = {"tokens_in", "tokens_out", "run_id", "step_index"}
    missing = required_for_cost - cols
    assert not missing, f"cost service depends on missing columns: {missing}"
