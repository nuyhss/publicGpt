"""
Conversation memory repository helpers.
"""

from __future__ import annotations

from typing import List

import aiosqlite

from app.db.database import get_db_path
from app.models.schemas import Message


async def save_message(session_id: str, role: str, content: str) -> None:
    async with aiosqlite.connect(get_db_path()) as db:
        await db.execute(
            """
            INSERT INTO chat_messages (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, role, content),
        )
        await db.commit()


async def load_messages(session_id: str, limit: int = 40) -> List[Message]:
    async with aiosqlite.connect(get_db_path()) as db:
        async with db.execute(
            """
            SELECT role, content
            FROM (
                SELECT role, content, id
                FROM chat_messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [Message(role=row[0], content=row[1]) for row in rows]
