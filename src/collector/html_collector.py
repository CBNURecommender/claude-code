"""HTML article parser with source-specific CSS selectors.

Each known news source has a dedicated selector config that targets the main
article list area, avoiding navigation/sidebar/footer noise.  Unknown sources
fall back to the generic heuristic (URL pattern matching on all <a> tags).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from src.utils.logger import get_logger

logger = get_logger("collector.html")


# ---------------------------------------------------------------------------
# Source-specific selector configs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SourceSelector:
    """CSS selector config for a specific news source."""
    container: str          # CSS selector for the article list container
    link: str | None = None # CSS selector for article links within container (None = all <a>)
    url_pattern: str | None = None  # Regex pattern article URLs must match
    min_title_length: int = 10


# Key: domain substring that uniquely identifies the source
_SOURCE_SELECTORS: dict[str, SourceSelector] = {
    "etnews.com": SourceSelector(
        container="ul.news_list",
        link="li a",
        url_pattern=r"/\d{14}",
    ),
    "thelec.kr": SourceSelector(
        container="article.altlist-body",
        link="a[href*='articleView']",
    ),
    "zdnet.co.kr": SourceSelector(
        container="div.contentWrapper",
        link="a[href*='/view/']",
        url_pattern=r"/view/\?no=\d+",
    ),
    "hankyung.com": SourceSelector(
        container="ul.news-list",
        link="a[href*='/article/']",
    ),
    "trendforce.com": SourceSelector(
        container="div.news-list, div.content-area, main",
        link="a[href*='/news/']",
    ),
    "digitimes.com": SourceSelector(
        container="div.news-frame, div.main-content, main",
        link="a[href*='/news/a']",
    ),
    "omdia.tech.informa.com": SourceSelector(
        container="div.search-results, div.content-listing, main",
        link="a[href*='/pr/']",
    ),
    "counterpointresearch.com": SourceSelector(
        container="div.insights-list, div.post-listing, main",
        link="a[href*='/insights/']",
    ),
    "semianalysis.com": SourceSelector(
        container="div.post-list, main, div.content",
        link="a[href*='/p/']",
    ),
    "asia.nikkei.com": SourceSelector(
        container="body",
        link=None,
        url_pattern=r"nikkei\.com/.+/.+/.+",
        min_title_length=20,
    ),
    "thebell.co.kr": SourceSelector(
        container="div.newsBox",
        link="a[href*='newsview']",
        min_title_length=10,
    ),
    "datacenterdynamics.com": SourceSelector(
        container="main",
        link="a[href*='/news/']",
    ),
    "dealsite.co.kr": SourceSelector(
        container="main, div.content, body",
        link="a[href*='/articles/']",
    ),
}


# ---------------------------------------------------------------------------
# Generic fallback patterns (unchanged from original)
# ---------------------------------------------------------------------------
_ARTICLE_URL_PATTERNS = re.compile(
    r"(/news/|/article/|/story/|/post/|/blog/|/pr/|/insights/|"
    r"/\d{4}/\d{2}/|/\d{8}|/\d{6})",
    re.IGNORECASE,
)

_MIN_TITLE_LENGTH = 10

_NAV_TEXTS = {
    "home", "about", "contact", "login", "sign up", "register",
    "more", "next", "previous", "prev", "back", "menu",
    "홈", "로그인", "회원가입", "이전", "다음", "더보기",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _find_selector(url: str) -> SourceSelector | None:
    """Return the SourceSelector matching *url*, or None for unknown sources."""
    for domain, selector in _SOURCE_SELECTORS.items():
        if domain in url:
            return selector
    return None


def _extract_from_container(
    soup: BeautifulSoup,
    base_url: str,
    selector: SourceSelector,
) -> list[dict]:
    """Extract articles using source-specific CSS selectors."""
    articles: list[dict] = []
    seen_urls: set[str] = set()

    # Try each comma-separated container selector until one matches
    containers: list[Tag] = []
    for css in selector.container.split(","):
        css = css.strip()
        found = soup.select(css)
        if found:
            containers.extend(found)

    if not containers:
        logger.debug("No container matched for selectors: %s", selector.container)
        return []

    url_re = re.compile(selector.url_pattern) if selector.url_pattern else None

    for container in containers:
        if selector.link:
            links = container.select(selector.link)
        else:
            links = container.find_all("a", href=True)

        for a_tag in links:
            href = a_tag.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            abs_url = urljoin(base_url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme not in ("http", "https"):
                continue
            if abs_url in seen_urls:
                continue

            if url_re and not url_re.search(abs_url):
                continue

            title = a_tag.get_text(strip=True)
            if len(title) < selector.min_title_length:
                continue
            if title.lower() in _NAV_TEXTS:
                continue

            seen_urls.add(abs_url)
            articles.append({
                "title": title,
                "url": abs_url,
                "published_at": None,
            })

    return articles


def _extract_generic(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Fallback: scan all <a> tags with URL-pattern heuristic."""
    articles: list[dict] = []
    seen_urls: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue

        abs_url = urljoin(base_url, href)
        parsed = urlparse(abs_url)
        if parsed.scheme not in ("http", "https"):
            continue
        if abs_url in seen_urls:
            continue
        if not _ARTICLE_URL_PATTERNS.search(abs_url):
            continue

        title = a_tag.get_text(strip=True)
        if len(title) < _MIN_TITLE_LENGTH:
            continue
        if title.lower() in _NAV_TEXTS:
            continue

        seen_urls.add(abs_url)
        articles.append({
            "title": title,
            "url": abs_url,
            "published_at": None,
        })

    return articles


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def parse_html(url: str, *, timeout: float = 30.0) -> list[dict]:
    """Fetch and parse an HTML page for article links.

    Uses source-specific CSS selectors when the URL matches a known source,
    falling back to generic heuristic otherwise.
    """
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    selector = _find_selector(url)

    if selector:
        articles = _extract_from_container(soup, url, selector)
        if articles:
            logger.info(
                "Parsed %d articles from %s (source-specific selector)",
                len(articles), url,
            )
            return articles
        # Selector matched but found nothing -- fall through to generic
        logger.warning(
            "Source-specific selector matched no articles for %s, "
            "falling back to generic parser", url,
        )

    articles = _extract_generic(soup, url)
    logger.info("Parsed %d articles from %s (generic parser)", len(articles), url)
    return articles
