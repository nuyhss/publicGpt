"""
SQLite storage for raw messages.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("publicgpt.memory.db")

DDL = """
CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_session  ON messages(user_id, session_id);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(DDL)


def save_message(
    db_path: Path,
    user_id: str,
    session_id: str,
    role: str,
    content: str,
) -> str:
    msg_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO messages VALUES (?,?,?,?,?,?)",
            (msg_id, user_id, session_id, role, content, now),
        )
    return msg_id


def get_session_ids(db_path: Path, user_id: str, session_id: str) -> list[str]:
    """Return all message ids belonging to the current session."""
    with sqlite3.connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT id FROM messages WHERE user_id=? AND session_id=?",
            (user_id, session_id),
        ).fetchall()
    return [r[0] for r in rows]


def get_messages_by_ids(db_path: Path, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"SELECT * FROM messages WHERE id IN ({placeholders}) ORDER BY created_at ASC",
            ids,
        ).fetchall()
    return [dict(r) for r in rows]
