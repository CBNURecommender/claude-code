"""News Briefing System - Entry Point.

Starts the python-telegram-bot Application with JobQueue
on a single asyncio event loop. Database is initialized on startup.
"""

from __future__ import annotations

from src.utils.config import load_config
from src.utils.logger import get_logger, setup_logging
from src.storage.database import close_db, init_db
from telegram.ext import Application

logger = get_logger("main")


async def post_init(application: Application) -> None:
    """Called after Application.initialize() -- set up DB and log startup."""
    await init_db()
    logger.info("Database initialized")
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
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Future phases will register handlers here:
    # register_handlers(app)

    logger.info("Starting polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
