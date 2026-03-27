"""Claude API summarization module.

Batches all articles into a single Claude API call to produce one-line
Korean summaries in [핵심키워드] 요약문 — 출처 format.  On failure after
retries, returns a fallback list of raw article titles.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import anthropic

from src.utils.config import load_config
from src.utils.logger import get_logger

logger = get_logger("summarizer.briefing")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30

# ---------------------------------------------------------------------------
# System prompt (SOP Section 6-2, verbatim)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "당신은 IT/반도체 뉴스 요약 전문가입니다.\n"
    "각 기사를 아래 형식으로 한줄 요약하세요:\n"
    "[핵심키워드] 한줄 요약 — 출처\n"
    "핵심키워드는 기사의 가장 중요한 주제어 1~2개를 대괄호 안에 넣습니다.\n"
    "한줄 요약은 20~40자 이내로 핵심만 담습니다.\n"
    "출처는 뉴스 소스 이름입니다."
)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------
@dataclass
class ArticleForSummary:
    """Lightweight container for article data needed by the summarizer."""

    title: str
    url: str
    source_name: str


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def _build_user_prompt(articles: list[ArticleForSummary]) -> str:
    """Format articles as a numbered list for the Claude user prompt."""
    lines = ["아래 기사들을 각각 한줄 요약해주세요.", ""]
    for i, article in enumerate(articles, 1):
        lines.append(f"{i}. [{article.source_name}] {article.title}")
        lines.append(f"   URL: {article.url}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------
def _build_fallback(articles: list[ArticleForSummary]) -> str:
    """Return raw article titles when the Claude API is unavailable."""
    lines = ["[요약 실패 — 원본 제목 목록]", ""]
    for article in articles:
        lines.append(f"- {article.title} — {article.source_name}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core summarization function
# ---------------------------------------------------------------------------
async def summarize_articles(articles: list[ArticleForSummary]) -> str:
    """Summarize articles via a single batched Claude API call.

    Returns formatted summary text (multiple lines).
    On Claude API failure after retries, returns fallback title list.
    """
    if not articles:
        return ""

    config = load_config()
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
    user_prompt = _build_user_prompt(articles)

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            summary = response.content[0].text.strip()
            logger.info(f"Summarized {len(articles)} articles via Claude API")
            return summary

        except (anthropic.APIError, anthropic.APIConnectionError) as exc:
            last_error = exc
            logger.warning(
                f"Claude API attempt {attempt}/{MAX_RETRIES} failed: {exc}"
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    logger.error(
        f"Claude API failed after {MAX_RETRIES} retries, using fallback: {last_error}"
    )
    return _build_fallback(articles)
