"""Telegram command handlers for realtime alerts and AI provider control.

Provides /realtime_on, /realtime_off, /realtime_status,
/set_provider commands.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.storage.database import get_setting, set_setting
from src.utils.logger import get_logger

logger = get_logger("bot.realtime")


async def realtime_on_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Enable realtime link alerts."""
    await set_setting("realtime_enabled", "1")
    await update.message.reply_text("\u2705 실시간 알림이 활성화되었습니다.")
    logger.info("Realtime alerts enabled by user")


async def realtime_off_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Disable realtime link alerts."""
    await set_setting("realtime_enabled", "0")
    await update.message.reply_text("\u26d4 실시간 알림이 비활성화되었습니다.")
    logger.info("Realtime alerts disabled by user")


async def realtime_status_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show current realtime alert status."""
    enabled = await get_setting("realtime_enabled")
    provider = await get_setting("summary_provider") or "gemini"
    status = "ON \u2705" if enabled == "1" else "OFF \u26d4"
    await update.message.reply_text(
        f"실시간 알림: {status}\n"
        f"수집 주기: 5분\n"
        f"요약 AI: {provider}"
    )


async def set_provider_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /set_provider <anthropic|gemini> command."""
    if not context.args:
        current = await get_setting("summary_provider") or "gemini"
        await update.message.reply_text(
            f"현재 요약 AI: {current}\n"
            f"사용법: /set_provider <anthropic|gemini>"
        )
        return

    provider = context.args[0].lower().strip()
    if provider not in ("anthropic", "gemini"):
        await update.message.reply_text(
            "\u274c 지원하는 프로바이더: anthropic, gemini"
        )
        return

    await set_setting("summary_provider", provider)
    await update.message.reply_text(f"\u2705 요약 AI가 {provider}로 변경되었습니다.")
    logger.info(f"Summary provider changed to: {provider}")


def register_realtime_handlers(app: Application) -> None:
    """Register realtime alert and provider command handlers."""
    app.add_handler(CommandHandler("realtime_on", realtime_on_cmd))
    app.add_handler(CommandHandler("realtime_off", realtime_off_cmd))
    app.add_handler(CommandHandler("realtime_status", realtime_status_cmd))
    app.add_handler(CommandHandler("set_provider", set_provider_cmd))
    logger.info("Realtime handlers registered (4 commands)")
