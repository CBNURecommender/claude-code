"""RSS/Atom feed parser using feedparser.

Fetches and parses RSS/Atom feeds, extracting article title, URL, and published date.
Uses httpx to fetch the feed content (per D-01), then feedparser to parse it.
"""
from __future__ import annotations

from datetime import datetime
from time import mktime

import feedparser
import httpx

from src.utils.logger import get_logger

logger = get_logger("collector.rss")


async def parse_rss(url: str, *, timeout: float = 30.0) -> list[dict]:
    """Fetch and parse an RSS/Atom feed URL.

    Args:
        url: The exact RSS/Atom feed URL to fetch (per COL-03, only this URL).
        timeout: HTTP request timeout in seconds.

    Returns:
        List of article dicts: [{'title': str, 'url': str, 'published_at': str|None}]

    Raises:
        httpx.HTTPError: On network errors (caller should catch per COL-07).
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": "NewsBriefingBot/1.0"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    feed = feedparser.parse(response.text)

    articles = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            continue

        # Parse published date
        published_at = None
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if time_struct:
            try:
                published_at = datetime.fromtimestamp(mktime(time_struct)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            except (ValueError, OverflowError):
                pass

        articles.append({
            "title": title,
            "url": link,
            "published_at": published_at,
        })

    logger.info("Parsed %d articles from RSS feed: %s", len(articles), url)
    return articles
