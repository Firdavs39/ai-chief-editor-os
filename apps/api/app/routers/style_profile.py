from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from chief_editor.models import StyleProfile
from chief_editor.schemas import StyleProfileIn, StyleProfileOut

from ..deps import get_session

router = APIRouter(prefix="/style-profile", tags=["style"])


@router.get("", response_model=StyleProfileOut)
def get_profile(session: Session = Depends(get_session)) -> StyleProfileOut:
    profile = session.exec(
        select(StyleProfile).where(StyleProfile.name == "default")
    ).first()
    if profile is None:
        profile = StyleProfile(
            name="default",
            tone="",
            audience="",
            banned_phrases=[],
            example_posts=[],
            writing_rules="",
            target_topics=[],
            voice_sliders={},
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return StyleProfileOut(**profile.model_dump())


@router.put("", response_model=StyleProfileOut)
def update_profile(
    payload: StyleProfileIn,
    session: Session = Depends(get_session),
) -> StyleProfileOut:
    profile = session.exec(
        select(StyleProfile).where(StyleProfile.name == "default")
    ).first()
    if profile is None:
        profile = StyleProfile(name="default", **payload.model_dump())
    else:
        for k, v in payload.model_dump().items():
            setattr(profile, k, v)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return StyleProfileOut(**profile.model_dump())
