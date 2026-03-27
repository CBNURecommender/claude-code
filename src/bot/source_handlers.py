"""Telegram command handlers for news source management.

Provides /add_source, /remove_source (with confirmation), /list_sources,
/enable_source, and /disable_source commands. All responses are in Korean.
"""

from __future__ import annotations

import aiosqlite
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
)

from src.storage.queries import (
    add_source,
    disable_source,
    enable_source,
    get_source_by_name,
    list_source_keywords,
    list_sources,
    remove_source,
)
from src.utils.logger import get_logger

logger = get_logger("bot.sources")

# ConversationHandler states
CONFIRM_DELETE = 0


# ---------------------------------------------------------------------------
# /add_source <name> <URL>
# ---------------------------------------------------------------------------
async def add_source_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a new news source. Usage: /add_source <name> <URL>"""
    args = context.args
    if not args or len(args) != 2:
        await update.message.reply_text("사용법: /add_source <이름> <URL>")
        return

    name, url = args[0], args[1]

    if not url.startswith(("http://", "https://")):
        await update.message.reply_text(
            "올바른 URL을 입력하세요 (http:// 또는 https://로 시작)"
        )
        return

    try:
        await add_source(name, url)
    except aiosqlite.IntegrityError:
        await update.message.reply_text(f"이미 등록된 URL입니다: {url}")
        return

    logger.info(f"Source added via bot: {name} ({url})")
    await update.message.reply_text(
        f"소스 추가 완료\n"
        f"이름: {name}\n"
        f"URL: {url}\n"
        f"타입: auto (자동감지)\n"
        f"필터 키워드: 없음 (모든 기사 수집)\n"
        f"\n"
        f"필터 키워드를 설정하려면:\n"
        f"/add_keyword {name} <키워드>"
    )


# ---------------------------------------------------------------------------
# /remove_source <name> (with /confirm_delete confirmation)
# ---------------------------------------------------------------------------
async def remove_source_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int | None:
    """Start source removal with confirmation. Usage: /remove_source <name>"""
    args = context.args
    if not args or len(args) != 1:
        await update.message.reply_text("사용법: /remove_source <이름>")
        return ConversationHandler.END

    name = args[0]
    source = await get_source_by_name(name)
    if source is None:
        await update.message.reply_text(f"소스를 찾을 수 없습니다: {name}")
        return ConversationHandler.END

    keywords = await list_source_keywords(source["id"])
    context.user_data["pending_delete"] = source

    await update.message.reply_text(
        f"'{name}' 소스를 삭제하시겠습니까?\n"
        f"등록된 키워드 {len(keywords)}개도 함께 삭제됩니다.\n"
        f"삭제하려면 /confirm_delete 를 입력하세요.\n"
        f"취소하려면 /cancel 을 입력하세요."
    )
    return CONFIRM_DELETE


async def confirm_delete_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Confirm and execute source deletion."""
    source = context.user_data.get("pending_delete")
    if source is None:
        await update.message.reply_text("삭제할 소스가 없습니다.")
        return ConversationHandler.END

    source_name = source["name"]
    await remove_source(source["id"])
    context.user_data.pop("pending_delete", None)

    logger.info(f"Source removed via bot: {source_name}")
    await update.message.reply_text(f"소스 삭제 완료: {source_name}")
    return ConversationHandler.END


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the pending source deletion."""
    context.user_data.pop("pending_delete", None)
    await update.message.reply_text("삭제가 취소되었습니다.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /list_sources
# ---------------------------------------------------------------------------
async def list_sources_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """List all registered news sources with status and keyword info."""
    sources = await list_sources()
    if not sources:
        await update.message.reply_text("등록된 소스가 없습니다.")
        return

    lines: list[str] = [f"등록된 뉴스 소스 ({len(sources)}개)\n"]

    for idx, src in enumerate(sources, start=1):
        enabled_icon = "ON" if src["enabled"] else "OFF (비활성)"
        keywords = await list_source_keywords(src["id"])
        keyword_count = len(keywords)

        if keyword_count > 0:
            keyword_display = f"{', '.join(keywords)} ({keyword_count}개)"
        else:
            keyword_display = "없음 (전체 수집)"

        lines.append(
            f"{idx}. {enabled_icon} {src['name']}\n"
            f"   URL: {src['url']}\n"
            f"   키워드: {keyword_display}"
        )

    await update.message.reply_text("\n".join(lines))


# ---------------------------------------------------------------------------
# /enable_source <name>
# ---------------------------------------------------------------------------
async def enable_source_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Enable a disabled source. Usage: /enable_source <name>"""
    args = context.args
    if not args or len(args) != 1:
        await update.message.reply_text("사용법: /enable_source <이름>")
        return

    name = args[0]
    source = await get_source_by_name(name)
    if source is None:
        await update.message.reply_text(f"소스를 찾을 수 없습니다: {name}")
        return

    if source["enabled"]:
        await update.message.reply_text(f"이미 활성 상태입니다: {name}")
        return

    await enable_source(source["id"])
    logger.info(f"Source enabled via bot: {name}")
    await update.message.reply_text(f"소스 활성화 완료: {name}")


# ---------------------------------------------------------------------------
# /disable_source <name>
# ---------------------------------------------------------------------------
async def disable_source_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Disable a source without deleting it. Usage: /disable_source <name>"""
    args = context.args
    if not args or len(args) != 1:
        await update.message.reply_text("사용법: /disable_source <이름>")
        return

    name = args[0]
    source = await get_source_by_name(name)
    if source is None:
        await update.message.reply_text(f"소스를 찾을 수 없습니다: {name}")
        return

    if not source["enabled"]:
        await update.message.reply_text(f"이미 비활성 상태입니다: {name}")
        return

    await disable_source(source["id"])
    logger.info(f"Source disabled via bot: {name}")
    await update.message.reply_text(f"소스 비활성화 완료: {name}")


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------
def register_source_handlers(app: Application) -> None:
    """Register all source management handlers with the Application."""

    # ConversationHandler for the two-step delete flow
    delete_conv = ConversationHandler(
        entry_points=[CommandHandler("remove_source", remove_source_cmd)],
        states={
            CONFIRM_DELETE: [
                CommandHandler("confirm_delete", confirm_delete_cmd),
                CommandHandler("cancel", cancel_cmd),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
    )
    app.add_handler(delete_conv)

    # Simple command handlers
    app.add_handler(CommandHandler("add_source", add_source_cmd))
    app.add_handler(CommandHandler("list_sources", list_sources_cmd))
    app.add_handler(CommandHandler("enable_source", enable_source_cmd))
    app.add_handler(CommandHandler("disable_source", disable_source_cmd))
