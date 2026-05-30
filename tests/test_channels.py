"""Multi-channel architecture tests.

Covers (per the architect's quality bar):
- default-channel migration (idempotent) + source linking + backfill
- channel creation + source attach/detach via the API
- per-channel cluster selection in enqueue_run
- per-channel style + raw-item resolution in the workflow
- per-channel publish-target resolution
- isolation: a candidate for channel A never resolves to channel B's chat

The conftest `_isolated_db` fixture uses `create_all` directly (NOT init_db),
so the migration does NOT run automatically — tests opt in explicitly.
"""

from __future__ import annotations

from sqlmodel import select

from chief_editor.models import (
    Channel,
    ChannelSource,
    GenerationRun,
    PostCandidate,
    RawItem,
    Source,
    StyleProfile,
    TrendCluster,
    TrendSignal,
)
from chief_editor.services.channels import (
    DEFAULT_CHANNEL_SLUG,
    ensure_default_channel,
    get_default_channel,
    slugify,
)
from chief_editor.services.generation import enqueue_run

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_source(session, handle: str, weight: float = 5.0) -> Source:
    src = Source(kind="telegram", handle=handle, url="", title=handle, weight=weight)
    session.add(src)
    session.commit()
    session.refresh(src)
    return src


def _mk_cluster_from_source(session, source: Source, text: str, score: float) -> TrendCluster:
    """Create a cluster + one raw item + signal so the cluster traces back to
    `source` (this is what per-channel filtering keys off)."""
    raw = RawItem(
        source_id=source.id,
        external_id=f"ext-{source.handle}-{text[:8]}",
        title=text,
        body=text,
        text_hash=text,
    )
    session.add(raw)
    session.commit()
    session.refresh(raw)

    cluster = TrendCluster(representative_text=text, total_score=score)
    session.add(cluster)
    session.commit()
    session.refresh(cluster)

    session.add(TrendSignal(cluster_id=cluster.id, raw_item_id=raw.id, similarity=1.0))
    session.commit()
    return cluster


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_basic() -> None:
    assert slugify("BUAI UZ") == "buai-uz"
    assert slugify("  My Channel!! ") == "my-channel"
    assert slugify("") == "channel"
    assert slugify("---") == "channel"


# ---------------------------------------------------------------------------
# Default-channel migration
# ---------------------------------------------------------------------------


def test_ensure_default_channel_creates_one(session) -> None:
    assert get_default_channel(session) is None
    channel = ensure_default_channel(session)
    assert channel.is_default is True
    assert channel.slug == DEFAULT_CHANNEL_SLUG
    assert channel.bot_provider == "telegram_bot"
    assert channel.platform == "telegram"


def test_ensure_default_channel_is_idempotent(session) -> None:
    c1 = ensure_default_channel(session)
    c2 = ensure_default_channel(session)
    assert c1.id == c2.id
    channels = list(session.exec(select(Channel)).all())
    assert len(channels) == 1


def test_default_channel_links_existing_style_profile(session) -> None:
    profile = StyleProfile(name="default", tone="x")
    session.add(profile)
    session.commit()
    session.refresh(profile)

    channel = ensure_default_channel(session)
    assert channel.style_profile_id == profile.id


def test_default_channel_links_all_existing_sources(session) -> None:
    s1 = _mk_source(session, "@a")
    s2 = _mk_source(session, "@b")
    channel = ensure_default_channel(session)

    links = list(
        session.exec(
            select(ChannelSource).where(ChannelSource.channel_id == channel.id)
        ).all()
    )
    linked_ids = {link.source_id for link in links}
    assert linked_ids == {s1.id, s2.id}


def test_default_channel_source_linking_is_idempotent(session) -> None:
    _mk_source(session, "@a")
    ensure_default_channel(session)
    ensure_default_channel(session)  # second run must not duplicate links
    links = list(session.exec(select(ChannelSource)).all())
    assert len(links) == 1


def test_migration_backfills_null_run_and_candidate_channel(session) -> None:
    # Legacy rows created before the channel model existed (channel_id NULL).
    run = GenerationRun(status="queued")
    cand = PostCandidate(topic="legacy")
    session.add(run)
    session.add(cand)
    session.commit()
    session.refresh(run)
    session.refresh(cand)
    assert run.channel_id is None
    assert cand.channel_id is None

    channel = ensure_default_channel(session)

    session.refresh(run)
    session.refresh(cand)
    assert run.channel_id == channel.id
    assert cand.channel_id == channel.id


def test_migration_does_not_overwrite_existing_channel_fk(session) -> None:
    channel = ensure_default_channel(session)
    other = Channel(name="other", slug="other")
    session.add(other)
    session.commit()
    session.refresh(other)

    run = GenerationRun(status="queued", channel_id=other.id)
    session.add(run)
    session.commit()
    session.refresh(run)

    ensure_default_channel(session)  # backfill pass
    session.refresh(run)
    # Already-assigned run keeps its channel — backfill only touches NULLs.
    assert run.channel_id == other.id
    assert run.channel_id != channel.id


# ---------------------------------------------------------------------------
# StyleProfile.name no longer unique
# ---------------------------------------------------------------------------


def test_style_profile_name_no_longer_unique(session) -> None:
    """Multi-channel needs more than one profile; name is now non-unique."""
    p1 = StyleProfile(name="default", tone="a")
    p2 = StyleProfile(name="default", tone="b")
    session.add(p1)
    session.add(p2)
    session.commit()  # must NOT raise IntegrityError
    rows = list(session.exec(select(StyleProfile).where(StyleProfile.name == "default")).all())
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Per-channel cluster selection in enqueue_run
# ---------------------------------------------------------------------------


def test_enqueue_run_stamps_default_channel_when_unspecified(session) -> None:
    channel = ensure_default_channel(session)
    src = _mk_source(session, "@a")
    # Link the new source to the default channel (it was created after migration).
    session.add(ChannelSource(channel_id=channel.id, source_id=src.id))
    session.commit()
    _mk_cluster_from_source(session, src, "тренд", 9.0)

    runs = enqueue_run(session, top_n=1, requested_by="manual")
    assert len(runs) == 1
    assert runs[0].channel_id == channel.id


def test_enqueue_run_filters_clusters_by_channel_sources(session) -> None:
    """Channel A's run must only pick clusters traceable to A's sources."""
    src_a = _mk_source(session, "@a")
    src_b = _mk_source(session, "@b")

    channel_a = Channel(name="A", slug="a", is_default=False)
    channel_b = Channel(name="B", slug="b", is_default=False)
    session.add(channel_a)
    session.add(channel_b)
    session.commit()
    session.refresh(channel_a)
    session.refresh(channel_b)

    session.add(ChannelSource(channel_id=channel_a.id, source_id=src_a.id))
    session.add(ChannelSource(channel_id=channel_b.id, source_id=src_b.id))
    session.commit()

    cluster_a = _mk_cluster_from_source(session, src_a, "из A", 5.0)
    cluster_b = _mk_cluster_from_source(session, src_b, "из B", 9.0)

    runs_a = enqueue_run(session, top_n=5, channel_id=channel_a.id, requested_by="manual")
    picked_a = {r.cluster_id for r in runs_a}
    # Even though cluster_b scores higher, channel A only sees cluster_a.
    assert picked_a == {cluster_a.id}
    assert cluster_b.id not in picked_a
    assert all(r.channel_id == channel_a.id for r in runs_a)


def test_enqueue_run_explicit_cluster_id_still_stamps_channel(session) -> None:
    channel = ensure_default_channel(session)
    src = _mk_source(session, "@a")
    cluster = _mk_cluster_from_source(session, src, "тренд", 1.0)
    runs = enqueue_run(session, cluster_id=cluster.id, channel_id=channel.id)
    assert len(runs) == 1
    assert runs[0].cluster_id == cluster.id
    assert runs[0].channel_id == channel.id


# ---------------------------------------------------------------------------
# Per-channel workflow reads (style + raw items)
# ---------------------------------------------------------------------------


def test_load_style_resolves_channel_profile(session) -> None:
    from chief_editor.services.generation import workflow

    default_profile = StyleProfile(name="default", tone="default-voice")
    chan_profile = StyleProfile(name="channel-a-voice", tone="A voice")
    session.add(default_profile)
    session.add(chan_profile)
    session.commit()
    session.refresh(chan_profile)

    channel = Channel(name="A", slug="a", style_profile_id=chan_profile.id)
    session.add(channel)
    session.commit()
    session.refresh(channel)

    run = GenerationRun(status="running", channel_id=channel.id)
    session.add(run)
    session.commit()
    session.refresh(run)

    style = workflow._load_style(session, run)
    assert style is not None
    assert style.id == chan_profile.id
    assert style.tone == "A voice"


def test_load_style_falls_back_to_default_for_legacy_run(session) -> None:
    from chief_editor.services.generation import workflow

    default_profile = StyleProfile(name="default", tone="default-voice")
    session.add(default_profile)
    session.commit()

    # Legacy run, no channel, no default channel present.
    run = GenerationRun(status="running", channel_id=None)
    session.add(run)
    session.commit()
    session.refresh(run)

    style = workflow._load_style(session, run)
    assert style is not None
    assert style.name == "default"


def test_load_raw_items_filters_by_channel_sources(session) -> None:
    """A cluster fed by sources from two channels must only surface the
    requesting channel's items — no cross-channel context leak into prompts."""
    from chief_editor.services.generation import workflow

    src_a = _mk_source(session, "@a")
    src_b = _mk_source(session, "@b")

    channel_a = Channel(name="A", slug="a")
    session.add(channel_a)
    session.commit()
    session.refresh(channel_a)
    session.add(ChannelSource(channel_id=channel_a.id, source_id=src_a.id))
    session.commit()

    # One cluster, two raw items: one from A's source, one from B's source.
    cluster = TrendCluster(representative_text="shared", total_score=1.0)
    session.add(cluster)
    session.commit()
    session.refresh(cluster)

    raw_a = RawItem(source_id=src_a.id, external_id="a1", title="A item", body="A", text_hash="a")
    raw_b = RawItem(source_id=src_b.id, external_id="b1", title="B item", body="B", text_hash="b")
    session.add(raw_a)
    session.add(raw_b)
    session.commit()
    session.refresh(raw_a)
    session.refresh(raw_b)
    session.add(TrendSignal(cluster_id=cluster.id, raw_item_id=raw_a.id))
    session.add(TrendSignal(cluster_id=cluster.id, raw_item_id=raw_b.id))
    session.commit()

    run = GenerationRun(status="running", channel_id=channel_a.id)
    session.add(run)
    session.commit()
    session.refresh(run)

    items = workflow._load_raw_items(session, cluster, run=run, limit=10)
    item_ids = {it.id for it in items}
    assert raw_a.id in item_ids
    assert raw_b.id not in item_ids  # B's source is NOT linked to channel A


def test_load_raw_items_unfiltered_for_legacy_run(session) -> None:
    """Legacy run (no channel, no default) keeps the prior unfiltered read."""
    from chief_editor.services.generation import workflow

    src = _mk_source(session, "@a")
    cluster = _mk_cluster_from_source(session, src, "тренд", 1.0)

    run = GenerationRun(status="running", channel_id=None)
    session.add(run)
    session.commit()
    session.refresh(run)

    items = workflow._load_raw_items(session, cluster, run=run, limit=10)
    assert len(items) == 1


# ---------------------------------------------------------------------------
# Finalizer stamps channel
# ---------------------------------------------------------------------------


def test_finalizer_stamps_candidate_channel(session) -> None:
    from chief_editor.services.generation.finalizer import finalize_candidate

    channel = ensure_default_channel(session)
    run = GenerationRun(status="running", channel_id=channel.id)
    session.add(run)
    session.commit()
    session.refresh(run)

    # Provide the two prerequisite artifacts the finalizer reads.
    _stage_finalizer_prereqs(session, run)

    result = finalize_candidate(session, run)
    session.commit()
    cand = session.get(PostCandidate, result["candidate_id"])
    assert cand is not None
    assert cand.channel_id == channel.id


def _stage_finalizer_prereqs(session, run) -> None:
    """Create the minimal final_brief + quality_report artifacts the finalizer
    consumes (read via get_run_artifacts_by_name). Attached to throwaway steps."""
    from chief_editor.models import GenerationArtifact, GenerationStep

    step = GenerationStep(run_id=run.id, step_index=0, name="editor_in_chief_finalizer")
    session.add(step)
    session.commit()
    session.refresh(step)
    session.add(
        GenerationArtifact(
            run_id=run.id,
            step_id=step.id,
            name="final_brief",
            payload={
                "topic": "тема",
                "source_summary": "сводка",
                "why_it_matters": "важно",
                "psychology_hook": "крючок",
                "final_tg": "телеграм текст",
                "final_threads": "threads текст",
                "final_reddit": "reddit текст",
                "cta": "подпишись",
            },
        )
    )

    step2 = GenerationStep(run_id=run.id, step_index=1, name="quality_judge")
    session.add(step2)
    session.commit()
    session.refresh(step2)
    session.add(
        GenerationArtifact(
            run_id=run.id,
            step_id=step2.id,
            name="quality_report",
            payload={
                "style_match_score": 0.8,
                "viral_score": 0.7,
                "slop_risk": 0.1,
                "controversy_risk": 0.1,
                "recommendation": "approve",
            },
        )
    )
    session.commit()


# ---------------------------------------------------------------------------
# Per-channel publish-target resolution + isolation
# ---------------------------------------------------------------------------


def test_resolve_target_uses_candidate_channel(session) -> None:
    from worker.main import _resolve_target_chat_id

    channel_b = Channel(name="B", slug="b", target_chat_id="@channel_b")
    session.add(channel_b)
    session.commit()
    session.refresh(channel_b)

    cand = PostCandidate(topic="x", channel_id=channel_b.id)
    session.add(cand)
    session.commit()
    session.refresh(cand)

    assert _resolve_target_chat_id(session, cand) == "@channel_b"


def test_resolve_target_falls_back_to_default_when_candidate_has_no_channel(
    session,
) -> None:
    from worker.main import _resolve_target_chat_id

    # Default channel with an explicit target.
    channel = ensure_default_channel(session)
    channel.target_chat_id = "@default_chat"
    session.add(channel)
    session.commit()

    cand = PostCandidate(topic="legacy", channel_id=None)
    session.add(cand)
    session.commit()
    session.refresh(cand)

    assert _resolve_target_chat_id(session, cand) == "@default_chat"


def test_candidate_isolation_a_does_not_resolve_to_b(session) -> None:
    """The core safety property: candidate of channel A resolves to A's chat,
    never to B's chat — even when B is the default channel."""
    from worker.main import _resolve_target_chat_id

    default_b = ensure_default_channel(session)
    default_b.target_chat_id = "@b_default"
    session.add(default_b)
    session.commit()

    channel_a = Channel(name="A", slug="a", target_chat_id="@a_chat")
    session.add(channel_a)
    session.commit()
    session.refresh(channel_a)

    cand_a = PostCandidate(topic="A topic", channel_id=channel_a.id)
    session.add(cand_a)
    session.commit()
    session.refresh(cand_a)

    target = _resolve_target_chat_id(session, cand_a)
    assert target == "@a_chat"
    assert target != "@b_default"


def test_telegram_publisher_honors_target_override(monkeypatch) -> None:
    """The publisher's destination follows the channel target override while
    the bot token resolution path is unchanged."""
    from chief_editor.publishing.telegram import telegram_publisher_from_settings
    from chief_editor.settings import get_settings

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("TELEGRAM_TARGET_CHANNEL_ID", "@default_target")
    get_settings.cache_clear()

    pub = telegram_publisher_from_settings(target_override="@channel_a")
    assert pub is not None
    assert pub._target == "@channel_a"

    # No override → falls back to the configured default target.
    pub_default = telegram_publisher_from_settings()
    assert pub_default is not None
    assert pub_default._target == "@default_target"

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


def test_api_seed_creates_default_channel(client) -> None:
    client.post("/demo/seed")
    res = client.get("/channels")
    assert res.status_code == 200
    channels = res.json()
    assert len(channels) >= 1
    default = next(c for c in channels if c["is_default"])
    assert default["slug"] == DEFAULT_CHANNEL_SLUG
    # Seeded sources must be linked to the default channel.
    assert len(default["source_ids"]) >= 1


def test_api_create_channel(client) -> None:
    client.post("/demo/seed")
    res = client.post(
        "/channels",
        json={"name": "Second Channel", "target_chat_id": "@second", "lang": "ru"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Second Channel"
    assert body["slug"] == "second-channel"
    assert body["is_default"] is False
    assert body["target_chat_id"] == "@second"


def test_api_create_channel_rejects_duplicate_slug(client) -> None:
    client.post("/demo/seed")
    client.post("/channels", json={"name": "Dup", "slug": "dup"})
    res = client.post("/channels", json={"name": "Dup2", "slug": "dup"})
    assert res.status_code == 409


def test_api_patch_channel_updates_target_and_style(client) -> None:
    client.post("/demo/seed")
    created = client.post("/channels", json={"name": "Patchable"}).json()
    res = client.patch(
        f"/channels/{created['id']}",
        json={"target_chat_id": "@new_target", "enabled": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["target_chat_id"] == "@new_target"
    assert body["enabled"] is False


def test_api_cannot_disable_default_channel(client) -> None:
    client.post("/demo/seed")
    default = next(c for c in client.get("/channels").json() if c["is_default"])
    res = client.patch(f"/channels/{default['id']}", json={"enabled": False})
    assert res.status_code == 409


def test_api_attach_and_detach_source(client) -> None:
    client.post("/demo/seed")
    channel = client.post("/channels", json={"name": "Linker"}).json()
    assert channel["source_ids"] == []

    # Pick an existing seeded source.
    src = client.get("/sources").json()[0]
    res = client.post(f"/channels/{channel['id']}/sources", json={"source_id": src["id"]})
    assert res.status_code == 201
    assert src["id"] in res.json()["source_ids"]

    # Detach.
    res = client.delete(f"/channels/{channel['id']}/sources/{src['id']}")
    assert res.status_code == 204
    refreshed = client.get(f"/channels/{channel['id']}").json()
    assert src["id"] not in refreshed["source_ids"]


def test_api_attach_source_is_idempotent(client) -> None:
    client.post("/demo/seed")
    channel = client.post("/channels", json={"name": "Idem"}).json()
    src = client.get("/sources").json()[0]
    client.post(f"/channels/{channel['id']}/sources", json={"source_id": src["id"]})
    res = client.post(f"/channels/{channel['id']}/sources", json={"source_id": src["id"]})
    assert res.status_code == 201
    # Still exactly one link.
    assert res.json()["source_ids"].count(src["id"]) == 1


def test_api_attach_unknown_source_404(client) -> None:
    client.post("/demo/seed")
    channel = client.post("/channels", json={"name": "X"}).json()
    res = client.post(f"/channels/{channel['id']}/sources", json={"source_id": "nope"})
    assert res.status_code == 404


def test_api_get_unknown_channel_404(client) -> None:
    res = client.get("/channels/does-not-exist")
    assert res.status_code == 404
