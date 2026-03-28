"""News Briefing System - Entry Point.

Starts the python-telegram-bot Application with JobQueue
on a single asyncio event loop. Database is initialized on startup.
Scheduled collection and briefing delivery run at configured intervals/times.
"""
from __future__ import annotations

from telegram.ext import Application

from src.bot.delivery_handlers import register_delivery_handlers
from src.bot.keyword_handlers import register_keyword_handlers
from src.bot.realtime_handlers import register_realtime_handlers
from src.bot.source_handlers import register_source_handlers
from src.bot.system_handlers import register_system_handlers
from src.services.scheduler import setup_scheduled_jobs
from src.storage.database import close_db, init_db
from src.utils.config import load_config
from src.utils.logger import get_logger, setup_logging

logger = get_logger("main")


async def post_init(application: Application) -> None:
    """Called after Application.initialize() -- set up DB and schedule jobs."""
    await init_db()
    logger.info("Database initialized")

    await setup_scheduled_jobs(application)
    logger.info("Delivery handlers and scheduled jobs registered")

    logger.info("Bot application started successfully")


async def post_shutdown(application: Application) -> None:
    """Called during Application shutdown -- clean up resources."""
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
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Register bot command handlers
    register_delivery_handlers(app)
    register_source_handlers(app)
    register_keyword_handlers(app)
    register_realtime_handlers(app)
    register_system_handlers(app)
    logger.info("Bot command handlers registered")

    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
