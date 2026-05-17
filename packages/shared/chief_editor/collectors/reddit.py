"""Reddit collector via the official API (asyncpraw)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..models import Source
from ..settings import get_settings
from .base import CollectedItem, Collector

log = logging.getLogger(__name__)


class RedditCollector(Collector):
    name = "reddit"

    async def fetch(self, source: Source, limit: int = 50) -> list[CollectedItem]:
        settings = get_settings()
        if not settings.has_reddit:
            log.info("reddit credentials missing — skipping reddit collector")
            return []

        try:
            import asyncpraw  # type: ignore
        except ImportError:
            log.warning("asyncpraw not installed — skipping reddit collector")
            return []

        reddit = asyncpraw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
        )
        items: list[CollectedItem] = []
        try:
            handle = source.handle
            if handle.startswith("/r/"):
                handle = handle[3:]
            elif handle.startswith("r/"):
                handle = handle[2:]
            subreddit = await reddit.subreddit(handle)
            async for submission in subreddit.hot(limit=limit):
                items.append(
                    CollectedItem(
                        external_id=submission.id,
                        title=submission.title or "",
                        body=submission.selftext or "",
                        url=f"https://reddit.com{submission.permalink}",
                        lang="en",
                        engagement={
                            "upvotes": submission.score,
                            "comments": submission.num_comments,
                            "score_ratio": submission.upvote_ratio,
                        },
                        posted_at=datetime.fromtimestamp(submission.created_utc, tz=timezone.utc),
                    )
                )
        finally:
            await reddit.close()
        return items
