"""Telegram system info and utility command handlers.

Provides /help, /status, /list_times, /start commands, and automatic
chat_id capture middleware. All responses are in Korean.
"""

from __future__ import annotations

import json

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.storage import queries
from src.storage.database import get_setting
from src.utils.logger import get_logger

logger = get_logger("bot.system")


# ---------------------------------------------------------------------------
# Chat ID auto-capture middleware (BOT-05)
# ---------------------------------------------------------------------------
async def auto_register_chat_id(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """MessageHandler callback that runs on every message to capture chat_id."""
    if update.effective_chat is None:
        return

    newly_registered = await queries.register_chat_id(update.effective_chat.id)
    if newly_registered:
        logger.info(f"New chat_id registered: {update.effective_chat.id}")


# ---------------------------------------------------------------------------
# /help (and /start) command (BOT-01)
# ---------------------------------------------------------------------------
HELP_TEXT = """\
사용 가능한 명령어

=== 소스 관리 ===
/add_source <이름> <URL> - 뉴스 소스 추가
/remove_source <이름> - 뉴스 소스 삭제
/list_sources - 등록된 소스 목록 조회
/enable_source <이름> - 소스 활성화
/disable_source <이름> - 소스 비활성화

=== 소스별 필터 키워드 ===
/add_keyword <소스이름> <키워드> - 필터 키워드 추가
/remove_keyword <소스이름> <키워드> - 필터 키워드 삭제
/list_keywords <소스이름> - 키워드 목록 조회
/clear_keywords <소스이름> - 모든 키워드 삭제

=== 전체 공통 키워드 ===
/add_global <키워드> - 전체 공통 키워드 추가
/remove_global <키워드> - 전체 공통 키워드 삭제
/list_globals - 전체 공통 키워드 조회

=== 브리핑 시간 ===
/set_times <HH:MM> [HH:MM] ... - 브리핑 시간 설정
/list_times - 현재 브리핑 시간 조회

=== 즉시 실행 ===
/collect - 지금 즉시 전체 수집
/briefing - 지금 즉시 브리핑 생성
/status - 현재 상태 조회

=== 도움말 ===
/help - 이 도움말 표시"""


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display all available commands in Korean."""
    await update.message.reply_text(HELP_TEXT)


# ---------------------------------------------------------------------------
# /status command (BOT-02)
# ---------------------------------------------------------------------------
async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show system status: source counts, pending articles, briefing times."""
    active, disabled = await queries.count_sources_by_status()
    pending = await queries.count_pending_articles()

    raw_times = await get_setting("briefing_times")
    times: list[str] = json.loads(raw_times) if raw_times else []
    times_display = ", ".join(times) if times else "미설정"

    text = (
        f"시스템 상태\n"
        f"\n"
        f"소스: {active}개 활성 / {disabled}개 비활성\n"
        f"미브리핑 기사: {pending}건\n"
        f"브리핑 시간: {times_display} KST"
    )
    await update.message.reply_text(text)


# ---------------------------------------------------------------------------
# /list_times command (BOT-03)
# ---------------------------------------------------------------------------
async def list_times_cmd(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Show currently configured briefing times."""
    raw_times = await get_setting("briefing_times")
    times: list[str] = json.loads(raw_times) if raw_times else []

    if not times:
        await update.message.reply_text("브리핑 시간이 설정되지 않았습니다.")
        return

    lines = ["현재 브리핑 시간"]
    for t in times:
        lines.append(f"- {t} KST")

    await update.message.reply_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Handler registration
# ---------------------------------------------------------------------------
def register_system_handlers(app: Application) -> None:
    """Register system info handlers and chat_id auto-capture middleware."""

    # Chat ID auto-capture runs on every message in group -1
    # (before command handlers, does not consume the update)
    app.add_handler(
        MessageHandler(filters.ALL, auto_register_chat_id),
        group=-1,
    )

    # /start delegates to help (common Telegram bot pattern)
    app.add_handler(CommandHandler("start", help_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("list_times", list_times_cmd))

    logger.info("System handlers registered (4 commands + chat_id capture)")
