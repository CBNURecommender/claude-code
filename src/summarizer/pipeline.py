"""Briefing pipeline orchestration.

Fetches unbriefed articles from DB, summarizes via Claude API,
saves formatted .md file to briefings/ folder, marks articles as
briefed, and records the briefing in the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.storage.database import get_db, get_setting
from src.summarizer.briefing import ArticleForSummary, summarize_articles
from src.utils.logger import get_logger

logger = get_logger("summarizer.pipeline")

KST = ZoneInfo("Asia/Seoul")


# ---------------------------------------------------------------------------
# Result data class
# ---------------------------------------------------------------------------
@dataclass
class BriefingResult:
    """Result of a single briefing pipeline run."""

    article_count: int
    file_path: str | None      # None if no articles
    briefing_id: int | None    # None if no articles
    summary_text: str           # Formatted briefing content or "no articles" message


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
async def run_briefing_pipeline() -> BriefingResult:
    """Full pipeline: fetch -> summarize -> save .md -> update DB.

    Returns a BriefingResult describing what happened.
    """
    db = await get_db()

    # ------------------------------------------------------------------
    # Step 1: Fetch unbriefed articles
    # ------------------------------------------------------------------
    async with db.execute(
        "SELECT id, title, url, source_name FROM articles "
        "WHERE is_briefed = 0 "
        "ORDER BY collected_at ASC"
    ) as cursor:
        rows = await cursor.fetchall()

    # ------------------------------------------------------------------
    # Step 2: Handle zero articles (SOP Section 7-2)
    # ------------------------------------------------------------------
    if not rows:
        logger.info("No unbriefed articles found")
        return BriefingResult(
            article_count=0,
            file_path=None,
            briefing_id=None,
            summary_text="새로운 기사가 없습니다.",
        )

    # Collect IDs and build ArticleForSummary list
    article_ids: list[int] = [row["id"] for row in rows]
    article_list: list[ArticleForSummary] = [
        ArticleForSummary(
            title=row["title"],
            url=row["url"],
            source_name=row["source_name"],
        )
        for row in rows
    ]

    logger.info(f"Found {len(article_list)} unbriefed articles")

    # ------------------------------------------------------------------
    # Step 3: Call summarizer
    # ------------------------------------------------------------------
    summary_lines = await summarize_articles(article_list)

    # ------------------------------------------------------------------
    # Step 4: Format .md content (SOP Section 6-3)
    # ------------------------------------------------------------------
    now = datetime.now(KST)
    timestamp_display = now.strftime("%Y-%m-%d %H:%M")
    count = len(article_list)

    md_content = (
        f"# 뉴스 브리핑 | {timestamp_display}\n"
        f"\n"
        f"> 대상 기사: {count}건\n"
        f"\n"
        f"---\n"
        f"\n"
        f"{summary_lines}\n"
        f"\n"
        f"---\n"
        f"\n"
        f"총 {count}건 | 생성: {timestamp_display} KST\n"
    )

    # ------------------------------------------------------------------
    # Step 5: Save .md file (SOP Section 6-4, STR-01)
    # ------------------------------------------------------------------
    folder = await get_setting("briefing_folder") or "briefings"
    Path(folder).mkdir(parents=True, exist_ok=True)

    filename = now.strftime("%Y-%m-%d_%H-%M") + ".md"
    filepath = str(Path(folder) / filename)

    Path(filepath).write_text(md_content, encoding="utf-8")
    logger.info(f"Briefing saved to {filepath}")

    # ------------------------------------------------------------------
    # Step 6: Record briefing and mark articles (SUM-04)
    # ------------------------------------------------------------------
    generated_at = now.isoformat()

    cursor = await db.execute(
        "INSERT INTO briefings (generated_at, article_count, content_md, file_path, delivered) "
        "VALUES (?, ?, ?, ?, 0)",
        (generated_at, count, md_content, filepath),
    )
    briefing_id = cursor.lastrowid

    placeholders = ",".join("?" for _ in article_ids)
    await db.execute(
        f"UPDATE articles SET is_briefed = 1, briefing_id = ? "
        f"WHERE id IN ({placeholders})",
        [briefing_id, *article_ids],
    )
    await db.commit()

    logger.info(
        f"Marked {len(article_ids)} articles as briefed (briefing_id={briefing_id})"
    )

    # ------------------------------------------------------------------
    # Step 7: Return result
    # ------------------------------------------------------------------
    return BriefingResult(
        article_count=count,
        file_path=filepath,
        briefing_id=briefing_id,
        summary_text=md_content,
    )
