"""JobQueue-based scheduling for briefing delivery and collection.

Uses python-telegram-bot's built-in JobQueue (wraps APScheduler internally)
instead of a separate APScheduler instance, avoiding event loop conflicts.
Briefing times are stored in the DB settings table as a JSON array of "HH:MM"
strings in KST timezone.
"""

from __future__ import annotations

import datetime
import json
import os
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

from src.delivery.telegram_sender import (
    deliver_briefing,
    format_briefing_message,
    send_realtime_links,
    send_realtime_summaries,
    send_to_all_users,
)
from src.storage.database import get_setting, set_setting
from src.utils.logger import get_logger

KST = ZoneInfo("Asia/Seoul")

logger = get_logger("services.scheduler")


# ---------------------------------------------------------------------------
# Scheduled job callbacks
# ---------------------------------------------------------------------------
async def job_briefing(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled briefing job callback. Called by JobQueue at configured times."""
    bot = context.bot
    try:
        from src.summarizer.pipeline import run_briefing_pipeline

        result = await run_briefing_pipeline()

        if result.article_count == 0:
            await deliver_briefing(bot, "", 0)
        else:
            timestamp_str = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
            md_filename: str | None = None
            if result.file_path:
                md_filename = os.path.basename(result.file_path)
            msg = format_briefing_message(
                result.summary_text, result.article_count, timestamp_str, md_filename
            )
            await deliver_briefing(bot, msg, result.article_count)

        logger.info(
            "Briefing job completed: %d articles delivered", result.article_count
        )

    except Exception as e:
        logger.error(f"Scheduled briefing failed: {e}")
        try:
            await send_to_all_users(
                bot, f"\u26a0\ufe0f \ube0c\ub9ac\ud551 \uc0dd\uc131 \uc911 \uc624\ub958\uac00 \ubc1c\uc0dd\ud588\uc2b5\ub2c8\ub2e4: {e}"
            )
        except Exception:
            logger.error("Failed to send error notification to users")


async def job_collect(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled collection job callback. Called by JobQueue at configured intervals."""
    try:
        from src.collector import collect_all_sources

        result = await collect_all_sources()
        logger.info(f"Scheduled collection completed: {result['new_articles']} new articles")
    except Exception as e:
        logger.error(f"Scheduled collection failed: {e}")


async def job_realtime_collect(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled realtime collection: collect and send link alerts every 5 minutes."""
    try:
        from src.collector import collect_all_sources

        result = await collect_all_sources()
        new_articles = result.get("new_articles_list", [])

        if not new_articles:
            return

        # Check if realtime alerts are enabled
        enabled = await get_setting("realtime_enabled")
        if enabled != "1":
            logger.debug("Realtime alerts disabled, skipping send")
            return

        await send_realtime_links(context.bot, new_articles)
        # Follow up with content summaries
        await send_realtime_summaries(context.bot, new_articles)

    except Exception as e:
        logger.error(f"Realtime collection failed: {e}")


# ---------------------------------------------------------------------------
# Schedule management
# ---------------------------------------------------------------------------
async def update_briefing_schedule(application: Application) -> None:
    """Read briefing_times from DB and update JobQueue jobs.

    Called on startup and after /set_times to apply schedule changes
    immediately without restart.
    """
    job_queue = application.job_queue

    # Remove existing briefing jobs
    jobs = job_queue.get_jobs_by_name("briefing")
    for job in jobs:
        job.schedule_removal()

    # Read times from DB, default to ["08:00", "18:00"]
    raw = await get_setting("briefing_times")
    times: list[str] = json.loads(raw) if raw else ["08:00", "18:00"]

    # Schedule each time
    for t in times:
        hour, minute = map(int, t.split(":"))
        job_queue.run_daily(
            job_briefing,
            time=datetime.time(hour=hour, minute=minute, tzinfo=KST),
            name="briefing",
            data={"time": t},
        )

    logger.info(f"Briefing schedule updated: {times}")


async def setup_scheduled_jobs(application: Application) -> None:
    """Set up both collection interval and briefing schedule.

    Called once from post_init after Application is built.
    """
    job_queue = application.job_queue

    # Collection interval job
    raw_interval = await get_setting("collection_interval_minutes")
    interval = int(raw_interval) if raw_interval else 30
    job_queue.run_repeating(
        job_collect,
        interval=interval * 60,
        first=10,
        name="collector",
    )
    logger.info("Scheduled collection every %d minutes", interval)

    # Realtime collection job (5-minute interval)
    job_queue.run_repeating(
        job_realtime_collect,
        interval=5 * 60,
        first=30,
        name="realtime_collector",
    )
    logger.info("Scheduled realtime collection every 5 minutes")

    # Briefing schedule
    await update_briefing_schedule(application)

    logger.info("Scheduled jobs initialized")
