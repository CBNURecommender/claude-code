"""Async query functions for sources, keywords, settings, and chat_ids.

Provides the data access layer used by all Telegram bot command handlers.
All functions use get_db() from src.storage.database for the shared connection.
"""

from __future__ import annotations

import json

import aiosqlite

from src.storage.database import get_db, get_setting, set_setting
from src.utils.logger import get_logger

logger = get_logger("storage.queries")


# ---------------------------------------------------------------------------
# Source CRUD
# ---------------------------------------------------------------------------
async def get_source_by_name(name: str) -> aiosqlite.Row | None:
    """Look up a source by name (case-insensitive)."""
    db = await get_db()
    async with db.execute(
        "SELECT * FROM sources WHERE name = ? COLLATE NOCASE", (name,)
    ) as cursor:
        return await cursor.fetchone()


async def get_source_by_id(source_id: int) -> aiosqlite.Row | None:
    """Look up a source by its integer ID."""
    db = await get_db()
    async with db.execute(
        "SELECT * FROM sources WHERE id = ?", (source_id,)
    ) as cursor:
        return await cursor.fetchone()


async def add_source(name: str, url: str) -> int:
    """Add a new source. Returns the new row ID.

    Raises aiosqlite.IntegrityError if the URL already exists.
    """
    db = await get_db()
    async with db.execute(
        "INSERT INTO sources (name, url) VALUES (?, ?)", (name, url)
    ) as cursor:
        lastrowid = cursor.lastrowid
    await db.commit()
    logger.info(f"Added source '{name}' (id={lastrowid})")
    return lastrowid


async def remove_source(source_id: int) -> None:
    """Delete a source by ID. CASCADE removes associated keywords."""
    db = await get_db()
    await db.execute("DELETE FROM sources WHERE id = ?", (source_id,))
    await db.commit()
    logger.info(f"Removed source id={source_id}")


async def list_sources() -> list[aiosqlite.Row]:
    """List all sources with their keyword count, ordered by name."""
    db = await get_db()
    async with db.execute(
        "SELECT s.*, "
        "(SELECT COUNT(*) FROM source_keywords sk WHERE sk.source_id = s.id) "
        "AS keyword_count FROM sources s ORDER BY s.name"
    ) as cursor:
        return await cursor.fetchall()


async def enable_source(source_id: int) -> None:
    """Enable a source for collection."""
    db = await get_db()
    await db.execute("UPDATE sources SET enabled = 1 WHERE id = ?", (source_id,))
    await db.commit()
    logger.info(f"Enabled source id={source_id}")


async def disable_source(source_id: int) -> None:
    """Disable a source from collection."""
    db = await get_db()
    await db.execute("UPDATE sources SET enabled = 0 WHERE id = ?", (source_id,))
    await db.commit()
    logger.info(f"Disabled source id={source_id}")


# ---------------------------------------------------------------------------
# Per-source keyword CRUD
# ---------------------------------------------------------------------------
async def add_source_keyword(source_id: int, keyword: str) -> bool:
    """Add a keyword to a source. Returns True if newly added, False if duplicate."""
    db = await get_db()
    async with db.execute(
        "INSERT OR IGNORE INTO source_keywords (source_id, keyword) VALUES (?, ?)",
        (source_id, keyword),
    ) as cursor:
        added = cursor.rowcount > 0
    await db.commit()
    return added


async def remove_source_keyword(source_id: int, keyword: str) -> bool:
    """Remove a keyword from a source. Returns True if removed, False if not found."""
    db = await get_db()
    async with db.execute(
        "DELETE FROM source_keywords WHERE source_id = ? AND keyword = ? COLLATE NOCASE",
        (source_id, keyword),
    ) as cursor:
        removed = cursor.rowcount > 0
    await db.commit()
    return removed


async def list_source_keywords(source_id: int) -> list[str]:
    """List all keywords for a given source, ordered alphabetically."""
    db = await get_db()
    async with db.execute(
        "SELECT keyword FROM source_keywords WHERE source_id = ? ORDER BY keyword",
        (source_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def clear_source_keywords(source_id: int) -> int:
    """Remove all keywords for a source. Returns the number deleted."""
    db = await get_db()
    async with db.execute(
        "DELETE FROM source_keywords WHERE source_id = ?", (source_id,)
    ) as cursor:
        count = cursor.rowcount
    await db.commit()
    return count


# ---------------------------------------------------------------------------
# Global keyword CRUD
# ---------------------------------------------------------------------------
async def add_global_keyword(keyword: str) -> bool:
    """Add a global keyword. Returns True if newly added, False if duplicate."""
    db = await get_db()
    async with db.execute(
        "INSERT OR IGNORE INTO global_keywords (keyword) VALUES (?)", (keyword,)
    ) as cursor:
        added = cursor.rowcount > 0
    await db.commit()
    return added


async def remove_global_keyword(keyword: str) -> bool:
    """Remove a global keyword. Returns True if removed, False if not found."""
    db = await get_db()
    async with db.execute(
        "DELETE FROM global_keywords WHERE keyword = ? COLLATE NOCASE", (keyword,)
    ) as cursor:
        removed = cursor.rowcount > 0
    await db.commit()
    return removed


async def list_global_keywords() -> list[str]:
    """List all global keywords, ordered alphabetically."""
    db = await get_db()
    async with db.execute(
        "SELECT keyword FROM global_keywords ORDER BY keyword"
    ) as cursor:
        rows = await cursor.fetchall()
    return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# Chat ID management
# ---------------------------------------------------------------------------
async def register_chat_id(chat_id: int) -> bool:
    """Register a Telegram chat ID. Returns True if newly added, False if already present."""
    raw = await get_setting("telegram_chat_ids")
    ids: list[str] = json.loads(raw) if raw else []
    chat_str = str(chat_id)
    if chat_str in ids:
        return False
    ids.append(chat_str)
    await set_setting("telegram_chat_ids", json.dumps(ids))
    logger.info(f"Registered chat_id {chat_id}")
    return True


async def get_chat_ids() -> list[int]:
    """Get all registered Telegram chat IDs as a list of ints."""
    raw = await get_setting("telegram_chat_ids")
    if not raw:
        return []
    ids: list[str] = json.loads(raw)
    return [int(cid) for cid in ids]


# ---------------------------------------------------------------------------
# Status / count helpers
# ---------------------------------------------------------------------------
async def count_pending_articles() -> int:
    """Count articles not yet included in a briefing."""
    db = await get_db()
    async with db.execute(
        "SELECT COUNT(*) FROM articles WHERE is_briefed = 0"
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row else 0


async def count_sources_by_status() -> tuple[int, int]:
    """Count sources by enabled status. Returns (active_count, disabled_count)."""
    db = await get_db()
    active = 0
    disabled = 0
    async with db.execute(
        "SELECT enabled, COUNT(*) FROM sources GROUP BY enabled"
    ) as cursor:
        rows = await cursor.fetchall()
    for row in rows:
        if row[0]:
            active = row[1]
        else:
            disabled = row[1]
    return (active, disabled)
