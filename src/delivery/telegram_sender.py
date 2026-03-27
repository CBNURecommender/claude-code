"""Telegram message delivery with splitting and multi-user support.

Sends briefing messages to all registered Telegram chat_ids,
splitting long messages at line boundaries to respect the 4096-char limit.
Handles the "no new articles" case with a Korean notification.
"""

from __future__ import annotations

import json

import telegram
from telegram.error import TelegramError

from src.storage.database import get_setting
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
