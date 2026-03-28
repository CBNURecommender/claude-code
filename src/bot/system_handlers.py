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
뉴스 브리핑 봇 사용 가이드

=== 소스 관리 ===
/add_source <이름> <URL>
  뉴스 소스를 추가합니다
  예) /add_source 테크크런치 https://techcrunch.com/feed/

/remove_source <이름>
  소스를 삭제합니다 (확인 질문 후 삭제)
  예) /remove_source 테크크런치

/list_sources
  등록된 전체 소스 목록을 조회합니다

/enable_source <이름>
  비활성화된 소스를 다시 켭니다
  예) /enable_source SemiAnalysis

/disable_source <이름>
  소스 수집을 중지합니다 (삭제 아님)
  예) /disable_source Omdia

=== 소스별 필터 키워드 ===
해당 소스에서 키워드가 포함된 기사만 수집합니다.
키워드가 없으면 모든 기사를 수집합니다.

/add_keyword <소스> <키워드>
  예) /add_keyword CNBC Technology semiconductor

/remove_keyword <소스> <키워드>
  예) /remove_keyword CNBC Technology semiconductor

/list_keywords <소스>
  예) /list_keywords CNBC Technology

/clear_keywords <소스>
  해당 소스의 키워드를 모두 삭제합니다

=== 전체 공통 키워드 ===
모든 소스에 공통 적용됩니다.
소스별 키워드 + 공통 키워드 중 하나라도 매칭되면 수집합니다.

/add_global <키워드>
  예) /add_global 반도체
  예) /add_global AI

/remove_global <키워드>
  예) /remove_global 반도체

/list_globals
  등록된 공통 키워드 목록을 조회합니다

=== 브리핑 시간 ===
/set_times <HH:MM> [HH:MM] ...
  브리핑 발송 시간을 설정합니다 (KST)
  예) /set_times 09:00 18:00
  예) /set_times 08:00 13:00 19:00

/list_times
  현재 설정된 브리핑 시간을 조회합니다

=== 즉시 실행 ===
/collect  - 전체 소스에서 지금 즉시 수집
/briefing - 미브리핑 기사를 요약하여 전송
/status   - 소스 수, 미브리핑 기사 수, 시간 조회

=== 실시간 알림 ===
/realtime_on     - 실시간 새 기사 링크 알림 + 내용 요약 켜기
/realtime_off    - 실시간 알림 끄기
/realtime_status - 실시간 알림 상태 확인

=== AI 설정 ===
/set_provider <anthropic|gemini>
  요약에 사용할 AI를 변경합니다
  예) /set_provider gemini

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

    realtime_enabled = await get_setting("realtime_enabled")
    realtime_status = "ON" if realtime_enabled == "1" else "OFF"

    text = (
        f"시스템 상태\n"
        f"\n"
        f"소스: {active}개 활성 / {disabled}개 비활성\n"
        f"미브리핑 기사: {pending}건\n"
        f"브리핑 시간: {times_display} KST\n"
        f"실시간 알림: {realtime_status} (5분 주기)"
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
