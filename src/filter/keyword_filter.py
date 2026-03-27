"""Keyword filtering for article titles.

Implements per-source and global keyword matching:
- Case-insensitive substring match on article titles
- 0 keywords = collect all articles (no filter)
- 1+ keywords = OR match (any keyword matches = pass)
- Global keywords combine with source keywords via OR
"""
from __future__ import annotations

from src.utils.logger import get_logger

logger = get_logger("filter.keyword")


def matches_keywords(title: str, keywords: list[str]) -> tuple[bool, list[str]]:
    """Check if a title matches any of the given keywords.

    Args:
        title: Article title to check.
        keywords: List of keywords to match against. Empty list = pass all.

    Returns:
        Tuple of (matched: bool, matched_keywords: list[str]).
        If keywords is empty, returns (True, []).
    """
    if not keywords:
        return True, []

    title_lower = title.lower()
    matched = [kw for kw in keywords if kw.lower() in title_lower]
    return bool(matched), matched


def filter_articles(
    articles: list[dict],
    source_keywords: list[str],
    global_keywords: list[str],
) -> list[dict]:
    """Filter articles by combined source + global keywords.

    Each article dict must have a 'title' key.
    Adds 'matched_keywords' key (JSON-serializable list) to passing articles.

    Args:
        articles: List of article dicts with at least {'title': str, 'url': str}.
        source_keywords: Per-source keywords.
        global_keywords: Global keywords applied to all sources.

    Returns:
        List of articles that passed the filter, each with 'matched_keywords' added.
    """
    combined_keywords = list(set(source_keywords + global_keywords))

    # No keywords at all = collect everything (per KWD-07)
    if not combined_keywords:
        for article in articles:
            article["matched_keywords"] = []
        logger.debug("No keywords configured — all %d articles pass", len(articles))
        return articles

    result = []
    for article in articles:
        matched, matched_kws = matches_keywords(article["title"], combined_keywords)
        if matched:
            article["matched_keywords"] = matched_kws
            result.append(article)

    logger.debug(
        "Keyword filter: %d/%d articles passed (keywords: %s)",
        len(result),
        len(articles),
        combined_keywords,
    )
    return result
