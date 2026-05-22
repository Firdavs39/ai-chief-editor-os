"""Phase 11 — Style DNA auto-learning (proposals, NOT silent updates).

Looks at recently approved+published PostCandidates and produces a
StyleProfile-update PROPOSAL that the operator reviews in `/style-dna`
and either accepts or rejects. The profile is NEVER mutated silently.

Safety properties:
- Reads only PostCandidate rows with status="published" (operator's
  explicit downstream action). Drafts/rejected/revised candidates do NOT
  feed back.
- Caps the number of source posts (top N most-recent) so a single biased
  approval burst can't dominate.
- Each proposal includes a `proposed_diff` so the operator can see exactly
  what would change.
- The proposal table (`StyleProposal`) is its own row; activating a
  proposal requires a separate operator action — no auto-apply.

This is scaffold for Phase 11. It DOES NOT call the LLM; the LLM-driven
diff generator is wired in a separate module when the proposal API ships.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from ..models import PostCandidate, StyleProfile

log = logging.getLogger(__name__)

# Cap: never learn from more than this many posts at once. Prevents a
# single approval session from drifting voice arbitrarily.
MAX_SOURCE_POSTS = 30


@dataclass
class StyleProposal:
    """A proposed change to the StyleProfile. Not persisted unless the
    operator accepts it via `/style-dna/proposals/{id}/accept`."""

    source_count: int
    current_profile_id: str
    current_tone: str
    current_banned_phrases: list[str]
    current_writing_rules: str
    proposed_tone: str
    proposed_banned_phrases: list[str]
    proposed_writing_rules: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_count": self.source_count,
            "current": {
                "profile_id": self.current_profile_id,
                "tone": self.current_tone,
                "banned_phrases": self.current_banned_phrases,
                "writing_rules": self.current_writing_rules,
            },
            "proposed": {
                "tone": self.proposed_tone,
                "banned_phrases": self.proposed_banned_phrases,
                "writing_rules": self.proposed_writing_rules,
            },
            "rationale": self.rationale,
        }


def _recent_published(session: Session, limit: int) -> list[PostCandidate]:
    return list(
        session.exec(
            select(PostCandidate)
            .where(PostCandidate.status == "published")
            .order_by(PostCandidate.updated_at.desc())
            .limit(limit)
        ).all()
    )


def _current_profile(session: Session) -> StyleProfile | None:
    return session.exec(
        select(StyleProfile).where(StyleProfile.name == "default")
    ).first()


def propose_style_update(session: Session) -> StyleProposal | None:
    """Build a StyleProposal from recent published posts.

    Returns None when there's nothing new to learn from (no published
    posts, or no profile to update).

    Phase 11 scaffold: the actual LLM-driven diff is intentionally STUB.
    A future PR plugs Haiku into the `rationale` generation; until then
    the proposal is a no-op snapshot that surfaces the COUNT of new
    examples but does not invent new rules.
    """
    profile = _current_profile(session)
    if profile is None:
        log.info("style_learning: no default profile — nothing to update")
        return None

    posts = _recent_published(session, MAX_SOURCE_POSTS)
    if not posts:
        log.info("style_learning: no published posts — nothing to learn from")
        return None

    # Stub: no auto-rule-generation yet. Return a proposal that mirrors
    # current state with a rationale explaining how many examples would
    # be used. This is enough to wire up the UI; the LLM step lands in a
    # follow-up PR. NOTHING gets silently changed.
    return StyleProposal(
        source_count=len(posts),
        current_profile_id=profile.id,
        current_tone=profile.tone,
        current_banned_phrases=list(profile.banned_phrases or []),
        current_writing_rules=profile.writing_rules,
        proposed_tone=profile.tone,
        proposed_banned_phrases=list(profile.banned_phrases or []),
        proposed_writing_rules=profile.writing_rules,
        rationale=(
            f"Phase 11 scaffold: {len(posts)} published posts available to "
            "learn from. No mutations proposed yet — the LLM-driven diff "
            "ships in a follow-up. Operator review required before any "
            "rule change."
        ),
    )


__all__ = ["MAX_SOURCE_POSTS", "StyleProposal", "propose_style_update"]
