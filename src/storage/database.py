"""Async SQLite database layer with schema creation and seed data.

Provides the persistent data layer for the news briefing system.
All operations use aiosqlite to avoid blocking the asyncio event loop.
"""

from __future__ import annotations

import aiosqlite

from src.utils.config import DATA_DIR, DB_PATH
from src.utils.logger import get_logger

logger = get_logger("storage.database")

# ---------------------------------------------------------------------------
# Module-level connection state
# ---------------------------------------------------------------------------
_connection: aiosqlite.Connection | None = None

# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------
_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    url         TEXT UNIQUE NOT NULL,
    type        TEXT DEFAULT 'auto',
    language    TEXT DEFAULT 'auto',
    enabled     BOOLEAN DEFAULT 1,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER NOT NULL,
    keyword     TEXT NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    UNIQUE(source_id, keyword)
);

CREATE TABLE IF NOT EXISTS global_keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword     TEXT UNIQUE NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS articles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    source_id       INTEGER NOT NULL,
    source_name     TEXT NOT NULL,
    summary         TEXT,
    published_at    DATETIME,
    collected_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    matched_keywords TEXT,
    is_briefed      BOOLEAN DEFAULT 0,
    briefing_id     INTEGER,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE INDEX IF NOT EXISTS idx_articles_briefed ON articles(is_briefed);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id);

CREATE TABLE IF NOT EXISTS briefings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    article_count   INTEGER,
    content_md      TEXT,
    file_path       TEXT,
    delivered       BOOLEAN DEFAULT 0,
    delivered_at    DATETIME
);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Default settings
# ---------------------------------------------------------------------------
_DEFAULT_SETTINGS = [
    ("briefing_times", '["08:00","18:00"]'),
    ("timezone", "Asia/Seoul"),
    ("briefing_folder", "briefings"),
    ("collection_interval_minutes", "30"),
    ("summary_language", "ko"),
    ("telegram_chat_ids", "[]"),
]

# ---------------------------------------------------------------------------
# Initial news sources (SOP Section 15)
# ---------------------------------------------------------------------------
INITIAL_SOURCES = [
    ("Tom's Hardware", "https://www.tomshardware.com/feeds.xml"),
    ("MacRumors", "https://feeds.macrumors.com/MacRumors-All"),
    ("CNBC Technology", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910"),
    ("WCCFTech", "https://wccftech.com/feed/"),
    ("전자신문", "https://www.etnews.com/news/section.html?id1=06"),
    ("디일렉", "https://www.thelec.kr/news/articleList.html?sc_section_code=S1N2&view_type=sm"),
    ("ZDNet Korea", "https://zdnet.co.kr/news/?lstcode=0050&page=1"),
    ("한국경제", "https://www.hankyung.com/industry/semicon-electronics"),
    ("TrendForce", "https://www.trendforce.com/news/"),
    ("DIGITIMES", "https://www.digitimes.com/tech/"),
    ("Omdia", "https://omdia.tech.informa.com/pr"),
    ("Counterpoint", "https://counterpointresearch.com/en/insights"),
    ("SemiAnalysis", "https://semianalysis.com/"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def get_db() -> aiosqlite.Connection:
    """Return the shared database connection.

    Raises RuntimeError if init_db() has not been called.
    """
    if _connection is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _connection


async def init_db() -> None:
    """Initialize the database: create tables, enable WAL, seed data.

    Safe to call multiple times -- uses IF NOT EXISTS and INSERT OR IGNORE
    so subsequent runs are idempotent.
    """
    global _connection  # noqa: PLW0603

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Open connection
    db = await aiosqlite.connect(str(DB_PATH))

    # Enable WAL mode for concurrent reads during writes
    await db.execute("PRAGMA journal_mode=WAL;")

    # Enable foreign key enforcement
    await db.execute("PRAGMA foreign_keys=ON;")

    # Enable Row factory for dict-like access
    db.row_factory = aiosqlite.Row

    # Create all tables
    await db.executescript(_SCHEMA_SQL)

    # Insert default settings (idempotent)
    for key, value in _DEFAULT_SETTINGS:
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )

    # Seed initial sources (idempotent)
    for name, url in INITIAL_SOURCES:
        await db.execute(
            "INSERT OR IGNORE INTO sources (name, url) VALUES (?, ?)",
            (name, url),
        )

    await db.commit()

    # Store as module-level connection
    _connection = db

    logger.info(f"Database initialized at {DB_PATH} (WAL mode)")
    logger.info(f"Seeded {len(INITIAL_SOURCES)} initial sources")


async def close_db() -> None:
    """Close the shared database connection."""
    global _connection  # noqa: PLW0603

    if _connection is not None:
        await _connection.close()
        _connection = None
        logger.info("Database connection closed")


# ---------------------------------------------------------------------------
# Setting helpers
# ---------------------------------------------------------------------------
async def get_setting(key: str) -> str | None:
    """Retrieve a setting value by key, or None if not found."""
    db = await get_db()
    async with db.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row else None


async def set_setting(key: str, value: str) -> None:
    """Insert or update a setting value."""
    db = await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    await db.commit()
