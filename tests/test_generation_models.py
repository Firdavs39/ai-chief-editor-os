"""SQLModel persistence tests for the Quality Editorial Workflow tables."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from chief_editor.models import (
    GenerationArtifact,
    GenerationRun,
    GenerationStep,
)


def test_generation_run_persists(session) -> None:
    run = GenerationRun(cluster_id=None, requested_by="api", status="queued")
    session.add(run)
    session.commit()
    session.refresh(run)
    assert run.id
    assert run.created_at and run.updated_at
    assert run.status == "queued"
    # Placeholder default; enqueue_run overwrites with live TOTAL_STEPS (11).
    assert run.total_steps == 11
    assert run.step_index == 0
    assert run.candidate_id is None


def test_generation_step_persists_and_unique_constraint(session) -> None:
    run = GenerationRun(requested_by="manual")
    session.add(run)
    session.commit()
    session.refresh(run)

    step0 = GenerationStep(run_id=run.id, step_index=0, name="research_analyst")
    session.add(step0)
    session.commit()

    # Unique (run_id, step_index) — second row at same index must fail.
    step0_dup = GenerationStep(run_id=run.id, step_index=0, name="trend_strategist")
    session.add(step0_dup)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_generation_artifact_persists_json_payload(session) -> None:
    run = GenerationRun(requested_by="api")
    session.add(run)
    session.commit()
    session.refresh(run)

    step = GenerationStep(run_id=run.id, step_index=0, name="research_analyst")
    session.add(step)
    session.commit()
    session.refresh(step)

    payload = {
        "editorial_rationale": "Свежий сигнал в нескольких источниках.",
        "fact_bullets": ["bullet 1", "bullet 2"],
        "source_handles": ["@source_a", "@source_b"],
        "gaps": ["нет численных данных"],
    }
    art = GenerationArtifact(
        run_id=run.id,
        step_id=step.id,
        name="research_brief",
        schema_version="v1",
        payload=payload,
    )
    session.add(art)
    session.commit()
    session.refresh(art)

    # Roundtrip JSON column intact.
    fetched = session.get(GenerationArtifact, art.id)
    assert fetched is not None
    assert fetched.payload["fact_bullets"] == ["bullet 1", "bullet 2"]
    assert fetched.payload["editorial_rationale"].startswith("Свежий")


def test_generation_run_status_transition_persists(session) -> None:
    run = GenerationRun(status="queued")
    session.add(run)
    session.commit()
    session.refresh(run)

    run.status = "running"
    run.current_step = "research_analyst"
    run.step_index = 1
    session.add(run)
    session.commit()
    session.refresh(run)

    assert run.status == "running"
    assert run.current_step == "research_analyst"


def test_generation_artifact_payload_must_be_dict(session) -> None:
    """The model is typed `dict[str, Any]`. Empty default round-trips fine."""
    run = GenerationRun()
    session.add(run)
    session.commit()
    session.refresh(run)
    step = GenerationStep(run_id=run.id, step_index=0, name="research_analyst")
    session.add(step)
    session.commit()
    session.refresh(step)

    art = GenerationArtifact(run_id=run.id, step_id=step.id, name="placeholder")
    session.add(art)
    session.commit()
    session.refresh(art)
    assert art.payload == {}


def test_all_three_models_listed_in_registry(session) -> None:
    """Sanity: SQLModel.metadata has the three tables registered so
    SQLModel.metadata.create_all already built them in the test fixture."""
    # If the model imports were missing from models/__init__.py the autouse
    # _isolated_db fixture would have raised before the test ran.
    assert session.exec(select(GenerationRun)).all() == []
    assert session.exec(select(GenerationStep)).all() == []
    assert session.exec(select(GenerationArtifact)).all() == []
