"""
SQLite persistence for chat messages and long-term memories.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Iterator, List, Optional

from app.config import DATABASE_PATH

_DB_LOCK = Lock()
DEFAULT_USER_ID = "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_user_id(user_id: Optional[str]) -> str:
    raw = (user_id or "").strip()
    if not raw or raw in {".", ".."}:
        return DEFAULT_USER_ID
    return raw[:120]


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    with _DB_LOCK, _connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;

            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                chat_id TEXT,
                role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant')),
                content TEXT NOT NULL,
                model TEXT,
                mode TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER NOT NULL DEFAULT 1,
                source_message_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (source_message_id) REFERENCES messages(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_user_chat_created
                ON messages(user_id, chat_id, created_at);

            CREATE INDEX IF NOT EXISTS idx_memories_user_updated
                ON memories(user_id, updated_at);
            """
        )
        conn.commit()


def ensure_user(user_id: Optional[str]) -> str:
    normalized = normalize_user_id(user_id)
    with _DB_LOCK, _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, created_at) VALUES (?, ?)",
            (normalized, _now_iso()),
        )
        conn.commit()
    return normalized


def add_message(
    *,
    user_id: Optional[str],
    chat_id: Optional[str],
    role: str,
    content: str,
    model: Optional[str] = None,
    mode: Optional[str] = None,
) -> int:
    normalized = ensure_user(user_id)
    with _DB_LOCK, _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages
                (user_id, chat_id, role, content, model, mode, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (normalized, chat_id, role, content, model, mode, _now_iso()),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_messages(
    *,
    user_id: Optional[str],
    chat_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    normalized = normalize_user_id(user_id)
    limit = max(1, min(int(limit or 100), 500))

    params: list[Any] = [normalized]
    where = "WHERE user_id = ?"
    if chat_id:
        where += " AND chat_id = ?"
        params.append(chat_id)
    params.append(limit)

    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, user_id, chat_id, role, content, model, mode, created_at
            FROM messages
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

    return [dict(row) for row in reversed(rows)]


def add_memory(
    *,
    user_id: Optional[str],
    content: str,
    importance: int = 1,
    source_message_id: Optional[int] = None,
) -> int:
    normalized = ensure_user(user_id)
    cleaned = content.strip()
    if not cleaned:
        raise ValueError("Memory content cannot be empty.")

    now = _now_iso()
    with _DB_LOCK, _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO memories
                (user_id, content, importance, source_message_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (normalized, cleaned, max(1, min(int(importance or 1), 5)), source_message_id, now, now),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_memories(*, user_id: Optional[str], limit: int = 20) -> List[Dict[str, Any]]:
    normalized = normalize_user_id(user_id)
    limit = max(1, min(int(limit or 20), 100))

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, content, importance, source_message_id, created_at, updated_at
            FROM memories
            WHERE user_id = ?
            ORDER BY importance DESC, updated_at DESC, id DESC
            LIMIT ?
            """,
            (normalized, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def delete_memory(*, user_id: Optional[str], memory_id: int) -> bool:
    normalized = normalize_user_id(user_id)
    with _DB_LOCK, _connect() as conn:
        cursor = conn.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, normalized),
        )
        conn.commit()
        return cursor.rowcount > 0


def maybe_extract_memory(text: str) -> Optional[str]:
    cleaned = (text or "").strip()
    lowered = cleaned.lower()
    triggers = [
        "remember ",
        "remember:",
        "please remember",
        "my name is ",
        "기억해",
        "기억해줘",
        "내 이름은",
        "앞으로",
    ]
    if not cleaned or not any(trigger in lowered or trigger in cleaned for trigger in triggers):
        return None
    return cleaned[:1000]

