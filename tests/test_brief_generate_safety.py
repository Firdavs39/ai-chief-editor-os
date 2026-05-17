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
