"""
SQLite database setup for conversation memory.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger("publicgpt.db.database")

_DB_PATH: Path | None = None


def init_db_path(data_dir: Path) -> None:
    global _DB_PATH
    data_dir.mkdir(parents=True, exist_ok=True)
    _DB_PATH = data_dir / "chat_memory.db"


def get_db_path() -> Path:
    if _DB_PATH is None:
        raise RuntimeError("Database path is not initialized.")
    return _DB_PATH


async def create_tables() -> None:
    db_path = get_db_path()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session
            ON chat_messages(session_id, id)
            """
        )
        await db.commit()
    logger.info("Chat memory DB ready: %s", db_path)
