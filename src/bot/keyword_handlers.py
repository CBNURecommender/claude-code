"""Telegram command handlers for per-source and global keyword management.

Implements KWD-01 through KWD-05: add/remove/list/clear per-source keywords
and add/remove/list global keywords. All responses are in Korean.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.storage import queries
from src.utils.logger import get_logger

logger = get_logger("bot.keywords")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
async def _resolve_source(
    update: Update, args: list[str], min_args: int, usage: str
) -> object | None:
    """Validate args count and resolve source by name.

    Replies with an error message if validation fails or source is not found.
    Returns the source row or None.
    """
    if len(args) < min_args:
        await update.message.reply_text(usage)
        return None

    source = await queries.get_source_by_name(args[0])
    if source is None:
        await update.message.reply_text(f"소스를 찾을 수 없습니다: {args[0]}")
        return None

    return source


# ---------------------------------------------------------------------------
# Per-source keyword commands (KWD-01 ~ KWD-04)
# ---------------------------------------------------------------------------
async def add_keyword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add_keyword <source_name> <keyword> — add a per-source keyword."""
    source = await _resolve_source(
        update, context.args, 2, "사용법: /add_keyword <소스이름> <키워드>"
    )
    if source is None:
        return

    keyword = " ".join(context.args[1:])
    added = await queries.add_source_keyword(source["id"], keyword)

    if not added:
        await update.message.reply_text(f"이미 등록된 키워드입니다: {keyword}")
        return

    keywords = await queries.list_source_keywords(source["id"])
    source_name = source["name"]
    await update.message.reply_text(
        f"'{source_name}'에 키워드 추가: {keyword}\n"
        f"현재 키워드: {', '.join(keywords)} ({len(keywords)}개)"
    )
    logger.info(f"Added keyword '{keyword}' to source '{source_name}'")


async def remove_keyword_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remove_keyword <source_name> <keyword> — remove a per-source keyword."""
    source = await _resolve_source(
        update, context.args, 2, "사용법: /remove_keyword <소스이름> <키워드>"
    )
    if source is None:
        return

    keyword = " ".join(context.args[1:])
    removed = await queries.remove_source_keyword(source["id"], keyword)

    if not removed:
        await update.message.reply_text(f"키워드를 찾을 수 없습니다: {keyword}")
        return

    keywords = await queries.list_source_keywords(source["id"])
    source_name = source["name"]

    if keywords:
        kw_display = f"{', '.join(keywords)} ({len(keywords)}개)"
    else:
        kw_display = "없음 (전체 수집 모드)"

    await update.message.reply_text(
        f"'{source_name}'에서 키워드 삭제: {keyword}\n"
        f"현재 키워드: {kw_display}"
    )
    logger.info(f"Removed keyword '{keyword}' from source '{source_name}'")


async def list_keywords_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list_keywords <source_name> — list keywords for a source."""
    source = await _resolve_source(
        update, context.args, 1, "사용법: /list_keywords <소스이름>"
    )
    if source is None:
        return

    keywords = await queries.list_source_keywords(source["id"])
    source_name = source["name"]

    if not keywords:
        await update.message.reply_text(
            f"'{source_name}'의 키워드: 없음 (전체 수집 모드)"
        )
    else:
        bullet_list = "\n".join(f"  - {kw}" for kw in keywords)
        await update.message.reply_text(
            f"'{source_name}'의 키워드 ({len(keywords)}개):\n{bullet_list}"
        )


async def clear_keywords_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /clear_keywords <source_name> — clear all keywords for a source."""
    source = await _resolve_source(
        update, context.args, 1, "사용법: /clear_keywords <소스이름>"
    )
    if source is None:
        return

    deleted_count = await queries.clear_source_keywords(source["id"])
    source_name = source["name"]

    if deleted_count == 0:
        await update.message.reply_text(
            f"'{source_name}'에 등록된 키워드가 없습니다."
        )
    else:
        await update.message.reply_text(
            f"'{source_name}'의 키워드 {deleted_count}개 삭제 완료\n"
            f"전체 수집 모드로 전환되었습니다."
        )
    logger.info(f"Cleared {deleted_count} keywords from source '{source_name}'")


# ---------------------------------------------------------------------------
# Global keyword commands (KWD-05)
# ---------------------------------------------------------------------------
async def add_global_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /add_global <keyword> — add a global keyword."""
    if not context.args:
        await update.message.reply_text("사용법: /add_global <키워드>")
        return

    keyword = " ".join(context.args)
    added = await queries.add_global_keyword(keyword)

    if not added:
        await update.message.reply_text(f"이미 등록된 전체 키워드입니다: {keyword}")
        return

    keywords = await queries.list_global_keywords()
    await update.message.reply_text(
        f"전체 공통 키워드 추가: {keyword}\n"
        f"현재 전체 키워드: {', '.join(keywords)} ({len(keywords)}개)"
    )
    logger.info(f"Added global keyword '{keyword}'")


async def remove_global_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remove_global <keyword> — remove a global keyword."""
    if not context.args:
        await update.message.reply_text("사용법: /remove_global <키워드>")
        return

    keyword = " ".join(context.args)
    removed = await queries.remove_global_keyword(keyword)

    if not removed:
        await update.message.reply_text(f"키워드를 찾을 수 없습니다: {keyword}")
        return

    await update.message.reply_text(f"전체 공통 키워드 삭제: {keyword}")
    logger.info(f"Removed global keyword '{keyword}'")


async def list_globals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /list_globals — list all global keywords."""
    keywords = await queries.list_global_keywords()

    if not keywords:
        await update.message.reply_text("등록된 전체 공통 키워드가 없습니다.")
    else:
        bullet_list = "\n".join(f"  - {kw}" for kw in keywords)
        await update.message.reply_text(
            f"전체 공통 키워드 ({len(keywords)}개):\n{bullet_list}"
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_keyword_handlers(app: Application) -> None:
    """Register all keyword management command handlers with the Application."""
    app.add_handler(CommandHandler("add_keyword", add_keyword_cmd))
    app.add_handler(CommandHandler("remove_keyword", remove_keyword_cmd))
    app.add_handler(CommandHandler("list_keywords", list_keywords_cmd))
    app.add_handler(CommandHandler("clear_keywords", clear_keywords_cmd))
    app.add_handler(CommandHandler("add_global", add_global_cmd))
    app.add_handler(CommandHandler("remove_global", remove_global_cmd))
    app.add_handler(CommandHandler("list_globals", list_globals_cmd))
    logger.info("Keyword management handlers registered (7 commands)")
