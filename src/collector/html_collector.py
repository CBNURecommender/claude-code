"""Generic HTML article parser using BeautifulSoup4 + lxml.

Extracts article links from HTML pages using common patterns:
- Links containing article-like URL patterns (/news/, /article/, /story/, date patterns)
- Filters out navigation/footer links (short text, common nav patterns)
- Converts relative URLs to absolute URLs
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from src.utils.logger import get_logger

logger = get_logger("collector.html")

# URL patterns that suggest an article link
_ARTICLE_URL_PATTERNS = re.compile(
    r"(/news/|/article/|/story/|/post/|/blog/|/pr/|/insights/|"
    r"/\d{4}/\d{2}/|/\d{8}|/\d{6})",
    re.IGNORECASE,
)

# Minimum title length to filter out navigation links
_MIN_TITLE_LENGTH = 10

# Common navigation link texts to exclude
_NAV_TEXTS = {
    "home", "about", "contact", "login", "sign up", "register",
    "more", "next", "previous", "prev", "back", "menu",
    "홈", "로그인", "회원가입", "이전", "다음", "더보기",
}


async def parse_html(url: str, *, timeout: float = 30.0) -> list[dict]:
    """Fetch and parse an HTML page for article links.

    Args:
        url: The exact HTML page URL to fetch (per COL-03, only this URL).
        timeout: HTTP request timeout in seconds.

    Returns:
        List of article dicts: [{'title': str, 'url': str, 'published_at': None}]

    Raises:
        httpx.HTTPError: On network errors (caller should catch per COL-07).
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    base_url = url
    articles = []
    seen_urls: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue

        # Convert relative to absolute URL
        abs_url = urljoin(base_url, href)

        # Skip non-HTTP URLs
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue

        # Skip duplicate URLs within this page
        if abs_url in seen_urls:
            continue

        # Check if URL looks like an article
        if not _ARTICLE_URL_PATTERNS.search(abs_url):
            continue

        # Extract title from link text
        title = a_tag.get_text(strip=True)

        # Filter out short/navigation texts
        if len(title) < _MIN_TITLE_LENGTH:
            continue
        if title.lower() in _NAV_TEXTS:
            continue

        seen_urls.add(abs_url)
        articles.append({
            "title": title,
            "url": abs_url,
            "published_at": None,  # HTML pages rarely have structured dates
        })

    logger.info("Parsed %d articles from HTML page: %s", len(articles), url)
    return articles
