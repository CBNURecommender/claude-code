"""Collection orchestrator -- fetches articles from all enabled sources.

Workflow per SOP Section 5-1:
1. Query all enabled sources from DB
2. For each source:
   a. Determine type (RSS/HTML) -- auto-detect if type='auto'
   b. Fetch and parse articles using appropriate parser
   c. Load source_keywords and global_keywords from DB
   d. Apply keyword filter
   e. Store new articles (deduplicate by URL via INSERT OR IGNORE)
3. Log results, skip failures per COL-07
"""
from __future__ import annotations

import json
from datetime import datetime

from src.collector.html_collector import parse_html
from src.collector.rss_collector import parse_rss
from src.collector.source_detector import detect_source_type
from src.filter.keyword_filter import filter_articles
from src.storage.database import get_db
from src.utils.logger import get_logger

logger = get_logger("collector")


async def collect_source(source: dict) -> list[dict]:
    """Collect articles from a single source.

    Args:
        source: Source row dict with keys: id, name, url, type, enabled.

    Returns:
        List of newly stored articles (each with title, url, source_name).
    """
    source_id = source["id"]
    source_name = source["name"]
    source_url = source["url"]
    source_type = source["type"]

    # Step 1: Determine source type if 'auto'
    if source_type == "auto":
        source_type = await detect_source_type(source_url)
        # Update the source type in DB so we don't re-detect next time
        db = await get_db()
        await db.execute(
            "UPDATE sources SET type = ? WHERE id = ?",
            (source_type, source_id),
        )
        await db.commit()
        logger.info("Auto-detected source type for '%s': %s", source_name, source_type)

    # Step 2: Parse articles using the appropriate parser
    if source_type == "rss":
        raw_articles = await parse_rss(source_url)
    else:
        raw_articles = await parse_html(source_url)

    if not raw_articles:
        logger.info("No articles found for source '%s'", source_name)
        return []

    # Step 3: Load keywords from DB
    db = await get_db()

    # Source-specific keywords
    async with db.execute(
        "SELECT keyword FROM source_keywords WHERE source_id = ?",
        (source_id,),
    ) as cursor:
        source_keywords = [row[0] for row in await cursor.fetchall()]

    # Global keywords
    async with db.execute("SELECT keyword FROM global_keywords") as cursor:
        global_keywords = [row[0] for row in await cursor.fetchall()]

    # Step 4: Apply keyword filter (per KWD-06, KWD-07, KWD-08)
    filtered_articles = filter_articles(raw_articles, source_keywords, global_keywords)

    if not filtered_articles:
        logger.info(
            "No articles passed keyword filter for source '%s' (%d raw articles)",
            source_name,
            len(raw_articles),
        )
        return []

    # Step 5: Store new articles with deduplication (per COL-04)
    new_count = 0
    new_articles: list[dict] = []
    for article in filtered_articles:
        matched_kw_json = json.dumps(
            article.get("matched_keywords", []), ensure_ascii=False
        )

        try:
            cursor = await db.execute(
                """INSERT OR IGNORE INTO articles
                   (url, title, source_id, source_name, published_at, matched_keywords)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    article["url"],
                    article["title"],
                    source_id,
                    source_name,
                    article.get("published_at"),
                    matched_kw_json,
                ),
            )
            # rowcount > 0 means the row was actually inserted (not ignored as duplicate)
            if cursor.rowcount > 0:
                new_count += 1
                new_articles.append({
                    "title": article["title"],
                    "url": article["url"],
                    "source_name": source_name,
                })
        except Exception as exc:
            logger.warning(
                "Failed to insert article '%s': %s", article["url"], exc
            )

    await db.commit()
    logger.info(
        "Source '%s': %d raw -> %d filtered -> %d new stored",
        source_name,
        len(raw_articles),
        len(filtered_articles),
        new_count,
    )
    return new_articles


async def collect_all_sources() -> dict:
    """Collect articles from all enabled sources.

    Returns:
        Summary dict: {
            'total_sources': int,
            'successful': int,
            'failed': int,
            'new_articles': int,
            'new_articles_list': list[dict],
            'errors': list[str],
        }
    """
    db = await get_db()

    async with db.execute(
        "SELECT id, name, url, type, enabled FROM sources WHERE enabled = 1"
    ) as cursor:
        sources = [dict(row) for row in await cursor.fetchall()]

    if not sources:
        logger.warning("No enabled sources found")
        return {
            "total_sources": 0,
            "successful": 0,
            "failed": 0,
            "new_articles": 0,
            "new_articles_list": [],
            "errors": [],
        }

    logger.info("Starting collection cycle for %d enabled sources", len(sources))

    total_new = 0
    successful = 0
    failed = 0
    errors: list[str] = []
    all_new_articles: list[dict] = []

    for source in sources:
        try:
            new_articles = await collect_source(source)
            total_new += len(new_articles)
            all_new_articles.extend(new_articles)
            successful += 1
        except Exception as exc:
            # Per COL-07: log and skip, do not block other sources
            error_msg = f"Source '{source['name']}' failed: {exc}"
            logger.error(error_msg)
            errors.append(error_msg)
            failed += 1

    logger.info(
        "Collection cycle complete: %d sources (%d ok, %d failed), %d new articles",
        len(sources),
        successful,
        failed,
        total_new,
    )

    return {
        "total_sources": len(sources),
        "successful": successful,
        "failed": failed,
        "new_articles": total_new,
        "new_articles_list": all_new_articles,
        "errors": errors,
    }
