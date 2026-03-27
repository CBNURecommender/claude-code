from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "news.db"
LOGS_DIR = PROJECT_ROOT / "logs"
BRIEFINGS_DIR = PROJECT_ROOT / "briefings"


@dataclass(frozen=True)
class Config:
    anthropic_api_key: str
    telegram_bot_token: str


def load_config() -> Config:
    load_dotenv(PROJECT_ROOT / ".env")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    missing = []
    if not api_key:
        missing.append("ANTHROPIC_API_KEY")
    if not bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")

    if missing:
        print(
            f"FATAL: Missing required environment variable(s): {', '.join(missing)}. "
            f"Set them in .env file at {PROJECT_ROOT / '.env'}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return Config(anthropic_api_key=api_key, telegram_bot_token=bot_token)
