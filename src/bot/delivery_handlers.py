"""Telegram bot command handlers for briefing delivery control.

Provides /set_times, /briefing, and /collect commands that allow users
to manage the briefing schedule and trigger immediate actions.
"""

from __future__ import annotations

import json
import re

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from src.delivery.telegram_sender import send_realtime_articles, send_to_all_users
from src.services.scheduler import job_briefing, update_briefing_schedule
from src.storage.database import get_setting, set_setting
from src.utils.logger import get_logger

logger = get_logger("bot.delivery_handlers")


# ---------------------------------------------------------------------------
# /set_times handler
# ---------------------------------------------------------------------------
async def set_times_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /set_times HH:MM [HH:MM] ... command.

    Validates time format, saves to DB, and immediately updates the
    JobQueue schedule so changes take effect without restart.
    """
    if not context.args:
        await update.message.reply_text(
            "\uc0ac\uc6a9\ubc95: /set_times 08:00 18:00\n"
            "\uc608\uc2dc: /set_times 07:30 12:00 19:00"
        )
        return

    time_pattern = re.compile(r"^\d{2}:\d{2}$")
    validated: list[str] = []

    for t in context.args:
        if not time_pattern.match(t):
            await update.message.reply_text(
                f"\uc798\ubabb\ub41c \uc2dc\uac04 \ud615\uc2dd: {t}. HH:MM \ud615\uc2dd\uc73c\ub85c \uc785\ub825\ud574\uc8fc\uc138\uc694."
            )
            return

        hour, minute = map(int, t.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            await update.message.reply_text(
                f"\uc798\ubabb\ub41c \uc2dc\uac04 \ud615\uc2dd: {t}. HH:MM \ud615\uc2dd\uc73c\ub85c \uc785\ub825\ud574\uc8fc\uc138\uc694."
            )
            return

        validated.append(t)

    sorted_times = sorted(validated)
    await set_setting("briefing_times", json.dumps(sorted_times))
    await update_briefing_schedule(context.application)

    times_display = ", ".join(sorted_times)
    await update.message.reply_text(
        f"\u2705 \ube0c\ub9ac\ud551 \uc2dc\uac04\uc774 \uc124\uc815\ub418\uc5c8\uc2b5\ub2c8\ub2e4: {times_display}"
    )
    logger.info(f"Briefing times updated to: {sorted_times}")


# ---------------------------------------------------------------------------
# /briefing handler
# ---------------------------------------------------------------------------
async def briefing_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /briefing command for immediate briefing generation and delivery."""
    await update.message.reply_text(
        "\u23f3 \ube0c\ub9ac\ud551\uc744 \uc0dd\uc131\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4..."
    )
    await job_briefing(context)


# ---------------------------------------------------------------------------
# /collect handler
# ---------------------------------------------------------------------------
async def collect_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /collect command for immediate article collection."""
    await update.message.reply_text(
        "\u23f3 \uae30\uc0ac\ub97c \uc218\uc9d1\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4..."
    )
    try:
        from src.collector import collect_all_sources

        result = await collect_all_sources()
        await update.message.reply_text(
            f"\u2705 \uc218\uc9d1 \uc644\ub8cc: {result['new_articles']}\uac74\uc758 \uc0c8 \uae30\uc0ac"
        )

        # Send realtime alerts if enabled and new articles exist
        new_articles = result.get("new_articles_list", [])
        if new_articles:
            enabled = await get_setting("realtime_enabled")
            if enabled == "1":
                await send_realtime_articles(context.bot, new_articles)
    except Exception as e:
        logger.error(f"Manual collection failed: {e}")
        await update.message.reply_text(
            f"\u274c \uc218\uc9d1 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4: {e}"
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_delivery_handlers(application) -> None:
    """Register all delivery-related command handlers with the bot application."""
    application.add_handler(CommandHandler("set_times", set_times_handler))
    application.add_handler(CommandHandler("briefing", briefing_handler))
    application.add_handler(CommandHandler("collect", collect_handler))
    logger.info("Delivery command handlers registered")
