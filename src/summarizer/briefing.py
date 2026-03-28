"""AI summarization module with Gemini API and Vertex AI fallback.

Provider priority: Gemini API (free tier) -> Vertex AI (GCP) -> fallback.
All summaries are forced to Korean output.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from src.utils.config import load_config
from src.utils.logger import get_logger

logger = get_logger("summarizer.briefing")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GEMINI_API_MODEL = "gemini-2.5-flash"  # Gemini API (free tier) - 최신 모델
VERTEX_MODEL = "gemini-2.5-flash"      # Vertex AI (GCP) - 동일 모델
VERTEX_PROJECT = "semi-korea-491110"
VERTEX_LOCATION = "us-central1"
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 5

# ---------------------------------------------------------------------------
# System prompt -- 한글 출력 강제
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = (
    "당신은 IT/반도체 뉴스 요약 전문가입니다.\n"
    "반드시 한국어로만 답변하세요. 영어 기사도 한국어로 요약하세요.\n"
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
    """Format articles as a numbered list for the user prompt."""
    lines = ["아래 기사들을 각각 한줄 요약해주세요. 반드시 한국어로 작성하세요.", ""]
    for i, article in enumerate(articles, 1):
        lines.append(f"{i}. [{article.source_name}] {article.title}")
        lines.append(f"   URL: {article.url}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------
def _build_fallback(articles: list[ArticleForSummary]) -> str:
    """Return raw article titles when the API is unavailable."""
    lines = ["[요약 실패 - 원본 제목 목록]", ""]
    for article in articles:
        lines.append(f"- {article.title} — {article.source_name}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gemini API (API key based — free tier)
# ---------------------------------------------------------------------------
async def _call_gemini(prompt: str, api_key: str) -> str | None:
    """Call Gemini API with API key. Returns text or None."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_API_MODEL}:generateContent?key={api_key}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            logger.warning(f"Gemini API attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    return None


# ---------------------------------------------------------------------------
# Vertex AI (GCP service account auth — no API key needed)
# ---------------------------------------------------------------------------
async def _get_gcp_access_token() -> str | None:
    """Fetch access token from GCP metadata server (only works on GCP instances)."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "http://metadata.google.internal/computeMetadata/v1/"
                "instance/service-accounts/default/token",
                headers={"Metadata-Flavor": "Google"},
            )
            resp.raise_for_status()
            return resp.json()["access_token"]
    except Exception:
        return None


async def _call_vertex(prompt: str) -> str | None:
    """Call Vertex AI Gemini. Returns text or None."""
    token = await _get_gcp_access_token()
    if not token:
        return None

    url = (
        f"https://{VERTEX_LOCATION}-aiplatform.googleapis.com/v1/"
        f"projects/{VERTEX_PROJECT}/locations/{VERTEX_LOCATION}/"
        f"publishers/google/models/{VERTEX_MODEL}:generateContent"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    url, json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as exc:
            logger.warning(f"Vertex AI attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    return None


# ---------------------------------------------------------------------------
# Generic text summarization (for realtime article content)
# ---------------------------------------------------------------------------
REALTIME_INSTRUCTION = (
    "아래 뉴스 기사 내용을 반드시 한국어로 3~4문장으로 간결하게 정리해주세요. "
    "영어 기사인 경우에도 반드시 한국어로 번역하여 요약하세요. "
    "핵심 내용만 포함하세요."
)


async def summarize_text(text: str, instruction: str | None = None) -> str | None:
    """Summarize arbitrary text. Tries Gemini API -> Vertex AI."""
    if instruction is None:
        instruction = REALTIME_INSTRUCTION

    config = load_config()
    prompt = f"{instruction}\n\n{text}"

    # 1. Gemini API (free tier)
    if config.google_api_key:
        result = await _call_gemini(prompt, config.google_api_key)
        if result:
            logger.info("Text summarized via Gemini API")
            return result

    # 2. Vertex AI (GCP fallback)
    result = await _call_vertex(prompt)
    if result:
        logger.info("Text summarized via Vertex AI")
        return result

    return None


# ---------------------------------------------------------------------------
# Core summarization function (Gemini -> Vertex -> fallback)
# ---------------------------------------------------------------------------
async def summarize_articles(articles: list[ArticleForSummary]) -> str:
    """Summarize articles. Tries Gemini API -> Vertex AI -> fallback."""
    if not articles:
        return ""

    config = load_config()
    user_prompt = _build_user_prompt(articles)
    full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

    # 1. Gemini API (free tier)
    if config.google_api_key:
        result = await _call_gemini(full_prompt, config.google_api_key)
        if result:
            logger.info(f"Summarized {len(articles)} articles via Gemini API")
            return result

    # 2. Vertex AI (GCP fallback)
    result = await _call_vertex(full_prompt)
    if result:
        logger.info(f"Summarized {len(articles)} articles via Vertex AI")
        return result

    logger.error("All AI providers failed, using fallback")
    return _build_fallback(articles)
