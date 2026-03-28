"""Telegram message delivery with splitting and multi-user support.

Sends briefing messages to all registered Telegram chat_ids,
splitting long messages at line boundaries to respect the 4096-char limit.
Handles the "no new articles" case with a Korean notification.
"""

from __future__ import annotations

import json

import httpx
import telegram
from telegram.error import TelegramError

from src.storage.database import get_db, get_setting
from src.utils.logger import get_logger

logger = get_logger("delivery.telegram_sender")

MAX_MESSAGE_LENGTH = 4096


# ---------------------------------------------------------------------------
# Message splitting
# ---------------------------------------------------------------------------
def split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into chunks respecting Telegram's character limit.

    Splits at line boundaries (newline characters) to avoid breaking
    mid-sentence. If a single line exceeds *max_length*, it is hard-split.

    Returns a list of chunks, each <= *max_length* characters.
    """
    if len(text) <= max_length:
        return [text]

    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        # +1 accounts for the newline we will rejoin with
        line_len = len(line)
        separator_len = 1 if current else 0

        if current_len + separator_len + line_len <= max_length:
            current.append(line)
            current_len += separator_len + line_len
        else:
            # Flush current chunk if it has content
            if current:
                chunks.append("\n".join(current))
                current = []
                current_len = 0

            # Handle single line exceeding max_length (defensive)
            if line_len > max_length:
                # Hard-split the long line
                pos = 0
                while pos < line_len:
                    chunks.append(line[pos : pos + max_length])
                    pos += max_length
            else:
                current.append(line)
                current_len = line_len

    # Flush remaining
    if current:
        chunks.append("\n".join(current))

    return chunks


# ---------------------------------------------------------------------------
# Multi-user delivery
# ---------------------------------------------------------------------------
async def send_to_all_users(bot: telegram.Bot, text: str) -> int:
    """Send a message (potentially split) to all registered chat_ids.

    Returns the count of successfully delivered chat_ids.
    """
    raw = await get_setting("telegram_chat_ids")
    if not raw:
        logger.warning("No registered chat_ids, skipping delivery")
        return 0

    chat_ids: list[str] = json.loads(raw)
    if not chat_ids:
        logger.warning("No registered chat_ids, skipping delivery")
        return 0

    chunks = split_message(text)
    success_count = 0

    for chat_id in chat_ids:
        try:
            for chunk in chunks:
                await bot.send_message(chat_id=int(chat_id), text=chunk)
            success_count += 1
        except TelegramError as exc:
            logger.warning(f"Failed to send to chat_id={chat_id}: {exc}")

    return success_count


# ---------------------------------------------------------------------------
# Briefing message formatting (SOP Section 7-1)
# ---------------------------------------------------------------------------
def format_briefing_message(
    summaries: str,
    article_count: int,
    timestamp_str: str,
    md_filename: str | None = None,
) -> str:
    """Format briefing content into the Telegram message format per SOP Section 7-1."""
    footer_extra = f" | 저장: {md_filename}" if md_filename else ""
    return (
        f"\U0001f4f0 뉴스 브리핑 | {timestamp_str}\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\n"
        f"{summaries}\n"
        f"\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"총 {article_count}건{footer_extra}"
    )


# ---------------------------------------------------------------------------
# High-level delivery function
# ---------------------------------------------------------------------------
async def deliver_briefing(
    bot: telegram.Bot, briefing_content: str, article_count: int
) -> int:
    """Deliver a briefing to all registered users.

    Called by the scheduler or ``/briefing`` command.

    * If *article_count* is 0, a simple Korean "no articles" message is sent
      without creating a ``.md`` file or recording in the briefings table
      (the caller handles that logic based on article_count).
    * Otherwise *briefing_content* (already formatted per SOP Section 7-1) is
      sent to all users.

    Returns the number of users successfully delivered to.
    """
    if article_count == 0:
        no_articles_msg = "\U0001f4ed 새로운 기사가 없습니다."
        count = await send_to_all_users(bot, no_articles_msg)
        logger.info(f"Briefing delivered to {count} users (0 articles)")
        return count

    count = await send_to_all_users(bot, briefing_content)
    logger.info(f"Briefing delivered to {count} users ({article_count} articles)")
    return count


# ---------------------------------------------------------------------------
# Realtime link alerts
# ---------------------------------------------------------------------------
def format_realtime_message(articles: list[dict]) -> str:
    """Format a list of new articles into the realtime alert message."""
    lines = ["\U0001f514 새 기사 알림", "\u2501" * 20, ""]
    for a in articles:
        lines.append(f"[{a['source_name']}] {a['title']}")
        lines.append(a["url"])
        lines.append("")
    lines.append("\u2501" * 20)
    lines.append(f"총 {len(articles)}건")
    return "\n".join(lines)


async def send_realtime_links(bot: telegram.Bot, articles: list[dict]) -> int:
    """Send realtime link alerts for new articles and mark them as sent.

    Args:
        bot: Telegram Bot instance.
        articles: List of dicts with keys: title, url, source_name.

    Returns:
        Number of users successfully delivered to.
    """
    if not articles:
        return 0

    msg = format_realtime_message(articles)
    count = await send_to_all_users(bot, msg)

    # Mark articles as realtime-sent in DB
    db = await get_db()
    urls = [a["url"] for a in articles]
    placeholders = ",".join("?" for _ in urls)
    await db.execute(
        f"UPDATE articles SET is_realtime_sent = 1 WHERE url IN ({placeholders})",
        urls,
    )
    await db.commit()

    logger.info(f"Realtime alerts sent to {count} users ({len(articles)} articles)")
    return count


# ---------------------------------------------------------------------------
# Realtime content summary (fetch + AI summarize)
# ---------------------------------------------------------------------------
async def _fetch_article_text(url: str) -> str | None:
    """Fetch article page and extract text content (first ~2000 chars)."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsBriefingBot/1.0)"
            })
            resp.raise_for_status()

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "lxml")
        # Remove script/style
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Truncate to ~2000 chars to keep API costs low
        return text[:2000] if text else None
    except Exception as exc:
        logger.debug(f"Failed to fetch article text from {url}: {exc}")
        return None


async def send_realtime_summaries(bot: telegram.Bot, articles: list[dict]) -> int:
    """Fetch article content, summarize in Korean, and send to users.

    Sent as a follow-up message after the link alert.
    """
    if not articles:
        return 0

    from src.summarizer.briefing import summarize_text

    summary_lines: list[str] = []

    for a in articles:
        content = await _fetch_article_text(a["url"])
        if content:
            summary = await summarize_text(content)
            if summary:
                summary_lines.append(f"[{a['source_name']}] {a['title']}")
                summary_lines.append(summary)
                summary_lines.append("")
                continue

        # Fallback: title only
        summary_lines.append(f"[{a['source_name']}] {a['title']}")
        summary_lines.append("(본문 요약 불가)")
        summary_lines.append("")

    if not summary_lines:
        return 0

    header = "\U0001f4dd 기사 내용 요약\n" + "\u2501" * 20 + "\n"
    footer = "\u2501" * 20
    msg = header + "\n".join(summary_lines) + footer

    count = await send_to_all_users(bot, msg)
    logger.info(f"Realtime summaries sent to {count} users ({len(articles)} articles)")
    return count
