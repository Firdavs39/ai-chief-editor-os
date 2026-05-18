"""POST /brief/generate is the public LLM smoke-generation endpoint.

It MUST:
- Use the configured provider via the registry (mock or real, both safe).
- Create new draft candidates and run the critic on them.
- NEVER create an ApprovalDecision automatically.
- NEVER create a PublishJob automatically.
- NEVER move a candidate to `approved` or `published` automatically.
"""

from __future__ import annotations

from sqlmodel import select

from chief_editor.models import (
    ApprovalDecision,
    PostCandidate,
    PublishJob,
)


def _seed(client) -> None:
    client.post("/demo/seed")


def test_brief_generate_returns_draft_candidates(client) -> None:
    _seed(client)
    res = client.post("/brief/generate", json={"top_n": 2})
    assert res.status_code == 200
    out = res.json()
    assert isinstance(out, list) and len(out) >= 1
    for c in out:
        assert c["status"] == "draft"
        assert isinstance(c["topic"], str) and c["topic"]
        assert isinstance(c["tg_version"], str) and c["tg_version"]
        # Critic has run — list shape exists even if empty.
        assert isinstance(c["critic_notes"], list)


def test_brief_generate_does_not_create_approval(client, session) -> None:
    _seed(client)
    before = len(session.exec(select(ApprovalDecision)).all())
    res = client.post("/brief/generate", json={"top_n": 1})
    assert res.status_code == 200
    after = len(session.exec(select(ApprovalDecision)).all())
    assert after == before, (
        f"/brief/generate must not create ApprovalDecision rows "
        f"(before={before}, after={after})"
    )


def test_brief_generate_does_not_create_publish_job(client, session) -> None:
    _seed(client)
    before = len(session.exec(select(PublishJob)).all())
    res = client.post("/brief/generate", json={"top_n": 1})
    assert res.status_code == 200
    after = len(session.exec(select(PublishJob)).all())
    assert after == before, (
        f"/brief/generate must not create PublishJob rows "
        f"(before={before}, after={after})"
    )


def test_brief_generate_does_not_mark_candidates_published(client, session) -> None:
    _seed(client)
    res = client.post("/brief/generate", json={"top_n": 3})
    assert res.status_code == 200
    fresh_ids = [c["id"] for c in res.json()]
    rows = session.exec(
        select(PostCandidate).where(PostCandidate.id.in_(fresh_ids))  # type: ignore[attr-defined]
    ).all()
    for c in rows:
        assert c.status == "draft", f"new candidate {c.id} must be draft, got {c.status}"


def test_brief_generate_works_with_mock_provider(client) -> None:
    """The mock provider must consistently produce valid candidates."""
    _seed(client)
    res = client.post("/brief/generate", json={"top_n": 1})
    cand = res.json()[0]
    # Mock provider returns Russian text by design (see chief_editor.llm.mock).
    assert any(ord(ch) > 127 for ch in cand["tg_version"]), (
        "mock LLM should produce Russian content"
    )
    # Recommended action is bounded.
    assert cand["recommendation"] in {"approve", "revise", "reject"}
    # Risk scores are bounded floats.
    for k in ("style_match_score", "viral_score", "slop_risk", "controversy_risk"):
        assert 0.0 <= cand[k] <= 1.0


# ---------------------------------------------------------------------------
# Real-provider backward-compat (Phase 1 of Quality Editorial Workflow).
# Real-provider mode must NOT call the LLM synchronously. It must enqueue
# GenerationRun rows and return HTTP 202 with {run_ids, status: "queued"}.
# ---------------------------------------------------------------------------


def test_brief_generate_real_mode_returns_202_with_run_ids(
    client, monkeypatch
) -> None:
    """Flip LLM_PROVIDER to a non-mock value with MOCK_MODE=false. The endpoint
    must NOT call generate_for_cluster — it enqueues and returns 202.

    We monkeypatch generate_for_cluster to raise if anyone touches it so a
    silent regression on the routing logic blows up loudly.
    """
    from chief_editor.services import candidate as candidate_module
    from chief_editor.settings import get_settings

    _seed(client)

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()

    def _boom(*_args, **_kwargs):
        raise AssertionError(
            "generate_for_cluster must NOT be called in real-provider mode "
            "from /brief/generate; the run should be enqueued instead"
        )

    monkeypatch.setattr(candidate_module, "generate_for_cluster", _boom)

    res = client.post("/brief/generate", json={"top_n": 2})
    assert res.status_code == 202, res.text
    body = res.json()
    assert body.get("candidates") is None
    assert body.get("status") == "queued"
    assert isinstance(body.get("run_ids"), list)
    assert len(body["run_ids"]) >= 1


def test_brief_generate_real_mode_creates_no_post_candidate(
    client, session, monkeypatch
) -> None:
    from chief_editor.settings import get_settings

    _seed(client)
    cand_before = len(session.exec(select(PostCandidate)).all())

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()

    res = client.post("/brief/generate", json={"top_n": 1})
    assert res.status_code == 202

    # Real mode is async — the request returns 202 with run_ids only.
    cand_after = len(session.exec(select(PostCandidate)).all())
    assert cand_after == cand_before, (
        f"real-provider /brief/generate must not create PostCandidate rows "
        f"(before={cand_before}, after={cand_after})"
    )


def test_brief_generate_real_mode_creates_no_approval_or_job(
    client, session, monkeypatch
) -> None:
    from chief_editor.settings import get_settings

    _seed(client)
    appr_before = len(session.exec(select(ApprovalDecision)).all())
    job_before = len(session.exec(select(PublishJob)).all())

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()

    client.post("/brief/generate", json={"top_n": 1})

    assert len(session.exec(select(ApprovalDecision)).all()) == appr_before
    assert len(session.exec(select(PublishJob)).all()) == job_before


def test_brief_generate_real_mode_does_not_call_llm_provider(
    client, monkeypatch
) -> None:
    """Belt-and-braces: even if a tester rewires the registry, the real-mode
    enqueue path should never reach get_llm_provider() because no generation
    happens on the request thread."""
    from chief_editor.llm import registry as llm_registry
    from chief_editor.settings import get_settings

    _seed(client)

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    get_settings.cache_clear()
    llm_registry.reset_provider_cache()

    calls = {"n": 0}
    real_get = llm_registry.get_llm_provider

    def _spy(*args, **kwargs):
        calls["n"] += 1
        return real_get(*args, **kwargs)

    monkeypatch.setattr(llm_registry, "get_llm_provider", _spy)

    res = client.post("/brief/generate", json={"top_n": 1})
    assert res.status_code == 202
    assert calls["n"] == 0, (
        f"real-provider /brief/generate must not invoke get_llm_provider; "
        f"got {calls['n']} calls"
    )
