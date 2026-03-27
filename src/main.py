"""News Briefing System - Entry Point.

Starts the python-telegram-bot Application with JobQueue
on a single asyncio event loop. Database is initialized on startup.
Scheduled collection runs at configured intervals.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.collector import collect_all_sources
from src.storage.database import close_db, get_setting, init_db
from src.utils.config import load_config
from src.utils.logger import get_logger, setup_logging

logger = get_logger("main")


async def job_collect(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled collection job — runs at configured interval."""
    logger.info("Scheduled collection starting...")
    result = await collect_all_sources()
    logger.info(
        "Scheduled collection done: %d sources (%d ok, %d failed), %d new articles",
        result["total_sources"],
        result["successful"],
        result["failed"],
        result["new_articles"],
    )


async def cmd_collect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/collect — trigger immediate collection (per COL-06)."""
    await update.message.reply_text("수집 시작...")

    result = await collect_all_sources()

    lines = [
        "수집 완료!",
        f"소스: {result['total_sources']}개 ({result['successful']}개 성공, {result['failed']}개 실패)",
        f"새 기사: {result['new_articles']}건",
    ]

    if result["errors"]:
        lines.append("")
        lines.append("오류:")
        for err in result["errors"]:
            lines.append(f"  - {err}")

    await update.message.reply_text("\n".join(lines))


async def post_init(application: Application) -> None:
    """Called after Application.initialize() — set up DB and schedule jobs."""
    await init_db()
    logger.info("Database initialized")

    # Schedule automatic collection (per COL-05)
    interval_str = await get_setting("collection_interval_minutes")
    interval_minutes = int(interval_str) if interval_str else 30

    application.job_queue.run_repeating(
        job_collect,
        interval=interval_minutes * 60,  # convert to seconds
        first=10,  # first run 10 seconds after startup
        name="collection_job",
    )
    logger.info("Scheduled collection every %d minutes", interval_minutes)

    logger.info("Bot application started successfully")


async def post_shutdown(application: Application) -> None:
    """Called during Application shutdown — clean up resources."""
    await close_db()
    logger.info("Shutdown complete")


def main() -> None:
    """Entry point: load config, set up logging, build and run the bot."""
    setup_logging()
    logger.info("Starting News Briefing System...")

    config = load_config()
    logger.info("Configuration loaded")

    app = (
        Application.builder()
        .token(config.telegram_bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Command handlers
    app.add_handler(CommandHandler("collect", cmd_collect))

    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
