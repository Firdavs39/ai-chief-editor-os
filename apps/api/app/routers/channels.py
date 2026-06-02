"""`/channels` router — manage outbound channels for multi-channel publishing.

A channel is one outbound destination (e.g. a Telegram channel) with its own
style profile and its own subset of parsing sources. These endpoints let an
operator create channels, point them at a chat, attach a style profile, and
wire up which sources feed each channel.

Security:
- `target_chat_id` is a PUBLIC identifier and is the only destination field
  stored on the channel. The bot token is NEVER accepted, stored, or returned
  here — it stays in the Integration Secrets Vault, resolved at publish time
  via `Channel.bot_provider`.
- The default channel cannot be disabled or deleted through these endpoints
  (deletion is intentionally not exposed at all in this slice).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from chief_editor.models import Channel, Source
from chief_editor.schemas import (
    ChannelCreate,
    ChannelOut,
    ChannelSourceLink,
    ChannelUpdate,
)
from chief_editor.services.channels import (
    channel_source_ids,
    link_source,
    slugify,
    unlink_source,
)

from ..deps import get_session, require_admin_token

router = APIRouter(prefix="/channels", tags=["channels"])

# Read endpoints stay open (consistent with /sources, /trends). Mutating
# endpoints are admin-token gated: changing a channel's target_chat_id
# redirects where approved content publishes, so it is higher-stakes than
# editing a source. The API is reachable over a public tunnel, so this is
# defense-in-depth, not just multi-tenant hygiene.


def _serialize(session: Session, channel: Channel) -> ChannelOut:
    return ChannelOut(
        id=channel.id,
        name=channel.name,
        slug=channel.slug,
        platform=channel.platform,
        target_chat_id=channel.target_chat_id,
        bot_provider=channel.bot_provider,
        lang=channel.lang,
        style_profile_id=channel.style_profile_id,
        enabled=channel.enabled,
        is_default=channel.is_default,
        settings=channel.settings or {},
        source_ids=channel_source_ids(session, channel.id),
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


def _get_or_404(session: Session, channel_id: str) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="channel_not_found")
    return channel


@router.get("", response_model=list[ChannelOut])
def list_channels(session: Session = Depends(get_session)) -> list[ChannelOut]:
    rows = session.exec(
        select(Channel).order_by(
            Channel.is_default.desc(), Channel.created_at.asc()
        )
    ).all()
    return [_serialize(session, c) for c in rows]


@router.post("", response_model=ChannelOut, status_code=201)
def create_channel(
    payload: ChannelCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin_token),
) -> ChannelOut:
    slug = slugify(payload.slug or payload.name)
    if session.exec(select(Channel).where(Channel.slug == slug)).first() is not None:
        raise HTTPException(status_code=409, detail="channel_slug_taken")

    channel = Channel(
        name=payload.name,
        slug=slug,
        platform=payload.platform,
        target_chat_id=payload.target_chat_id,
        bot_provider=payload.bot_provider,
        lang=payload.lang,
        style_profile_id=payload.style_profile_id,
        enabled=payload.enabled,
        is_default=False,  # only the migration creates the default channel
        settings=payload.settings,
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return _serialize(session, channel)


@router.get("/{channel_id}", response_model=ChannelOut)
def get_channel(
    channel_id: str, session: Session = Depends(get_session)
) -> ChannelOut:
    return _serialize(session, _get_or_404(session, channel_id))


@router.patch("/{channel_id}", response_model=ChannelOut)
def update_channel(
    channel_id: str,
    payload: ChannelUpdate,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin_token),
) -> ChannelOut:
    channel = _get_or_404(session, channel_id)
    data = payload.model_dump(exclude_unset=True)

    # Guard: never let the default channel be disabled — it is the fallback
    # destination for legacy / unassigned candidates.
    if channel.is_default and data.get("enabled") is False:
        raise HTTPException(
            status_code=409, detail="default_channel_cannot_be_disabled"
        )

    for key, value in data.items():
        setattr(channel, key, value)
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return _serialize(session, channel)


@router.post("/{channel_id}/sources", response_model=ChannelOut, status_code=201)
def attach_source(
    channel_id: str,
    payload: ChannelSourceLink,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin_token),
) -> ChannelOut:
    channel = _get_or_404(session, channel_id)
    if session.get(Source, payload.source_id) is None:
        raise HTTPException(status_code=404, detail="source_not_found")
    link_source(session, channel.id, payload.source_id)
    session.refresh(channel)
    return _serialize(session, channel)


@router.delete("/{channel_id}/sources/{source_id}", status_code=204, response_class=Response)
def detach_source(
    channel_id: str,
    source_id: str,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin_token),
) -> Response:
    _get_or_404(session, channel_id)
    removed = unlink_source(session, channel_id, source_id)
    if not removed:
        raise HTTPException(status_code=404, detail="link_not_found")
    return Response(status_code=204)
