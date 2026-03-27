"""Source type auto-detection (RSS vs HTML).

Determines how to fetch a source URL by checking:
1. URL path patterns (.xml, /feed, /rss, /atom)
2. HTTP Content-Type header (application/rss+xml, application/atom+xml)
3. Falls back to 'html' if detection fails or on network error.
"""
from __future__ import annotations

import re

import httpx

from src.utils.logger import get_logger

logger = get_logger("collector.source_detector")

_RSS_URL_PATTERNS = re.compile(r"(\.xml|/feed|/rss|/atom)", re.IGNORECASE)
_RSS_CONTENT_TYPES = {"application/rss+xml", "application/atom+xml", "text/xml", "application/xml"}


async def detect_source_type(url: str, *, timeout: float = 10.0) -> str:
    """Detect whether a URL is an RSS feed or HTML page.

    Args:
        url: The source URL to check.
        timeout: HTTP request timeout in seconds.

    Returns:
        'rss' or 'html'.
    """
    # Step 1: Check URL patterns
    if _RSS_URL_PATTERNS.search(url):
        logger.debug("URL pattern match for RSS: %s", url)
        return "rss"

    # Step 2: HTTP HEAD request to check Content-Type
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            response = await client.head(url)
            content_type = response.headers.get("content-type", "").lower().split(";")[0].strip()

            if content_type in _RSS_CONTENT_TYPES:
                logger.debug("Content-Type match for RSS: %s -> %s", url, content_type)
                return "rss"

    except (httpx.HTTPError, httpx.TimeoutException, Exception) as exc:
        logger.warning("Source type detection failed for %s: %s. Defaulting to html.", url, exc)

    logger.debug("Defaulting to HTML for: %s", url)
    return "html"
