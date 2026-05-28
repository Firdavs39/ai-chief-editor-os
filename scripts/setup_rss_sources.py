"""Phase 7 — register a default set of RSS sources.

Idempotent: if a source with the same URL already exists, it's skipped.
Zero-credentials. Safe to run any time.

Usage:
    python -m scripts.setup_rss_sources [--dry-run]
"""
from __future__ import annotations

import argparse
import sys

from sqlmodel import Session, select

from chief_editor.db import get_engine
from chief_editor.models import Source

DEFAULT_RSS_FEEDS: list[dict[str, str]] = [
    # Russian-language tech / marketing / content
    {"name": "vc.ru — Trends", "url": "https://vc.ru/rss", "lang": "ru"},
    {"name": "Habr — Top 24h", "url": "https://habr.com/ru/rss/articles/top/daily/?fl=ru",
     "lang": "ru"},
    {"name": "RB.RU — Startups", "url": "https://rb.ru/feeds/all/", "lang": "ru"},
    # English-language tech / marketing
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "lang": "en"},
    {"name": "Marketing Brew", "url": "https://www.marketingbrew.com/feed", "lang": "en"},
    {"name": "Stratechery", "url": "https://stratechery.com/feed/", "lang": "en"},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "lang": "en"},
    # Specialized
    {"name": "Anthropic Newsroom", "url": "https://www.anthropic.com/news/rss.xml",
     "lang": "en"},
    {"name": "Hacker News — Front Page",
     "url": "https://hnrss.org/frontpage", "lang": "en"},
    {"name": "MIT Tech Review", "url": "https://www.technologyreview.com/feed/",
     "lang": "en"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Register default RSS sources")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would be inserted, do nothing")
    args = parser.parse_args()

    engine = get_engine()
    with Session(engine) as session:
        existing_urls = {
            row.url for row in session.exec(select(Source).where(Source.kind == "rss")).all()
        }
        to_add: list[Source] = []
        for feed in DEFAULT_RSS_FEEDS:
            if feed["url"] in existing_urls:
                print(f"  skip (exists): {feed['name']}")
                continue
            to_add.append(
                Source(
                    kind="rss",
                    handle=feed["url"],  # `handle` is the unique-ish id; URL is fine
                    title=feed["name"],
                    url=feed["url"],
                    weight=5.0,
                    enabled=True,
                    health={"lang": feed["lang"], "poll_seconds": 600},
                )
            )

        if args.dry_run:
            print(f"DRY RUN — would add {len(to_add)} RSS sources:")
            for s in to_add:
                print(f"  + {s.title} ({s.url})")
            return 0

        for s in to_add:
            session.add(s)
        session.commit()
        print(f"phase7: registered {len(to_add)} new RSS sources "
              f"(skipped {len(existing_urls)} existing)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
