"""
Orchestrates SQLite + ChromaDB for long-term memory.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.memory.db import get_messages_by_ids, get_session_ids, save_message
from app.memory.vector_store import add_message, get_collection, search_similar

logger = logging.getLogger("publicgpt.memory")


class MemoryHandler:
    def __init__(self, db_path: Path, chroma_path: Path) -> None:
        self.db_path = db_path
        self.collection = get_collection(chroma_path)

    def save_turn(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        assistant_reply: str,
    ) -> None:
        try:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()

            uid = save_message(self.db_path, user_id, session_id, "user", user_message)
            add_message(self.collection, uid, user_message, user_id, now)

            aid = save_message(self.db_path, user_id, session_id, "assistant", assistant_reply)
            add_message(self.collection, aid, assistant_reply, user_id, now)
        except Exception as exc:
            logger.warning("save_turn failed: %s", exc)

    def get_long_term_context(
        self,
        user_id: str,
        current_session_id: str,
        current_message: str,
        n_results: int = 3,
    ) -> str:
        try:
            current_ids = get_session_ids(self.db_path, user_id, current_session_id)
            hits = search_similar(
                self.collection,
                query=current_message,
                user_id=user_id,
                n_results=n_results,
                exclude_ids=current_ids,
            )
            if not hits:
                return ""

            hit_ids = [h["id"] for h in hits]
            rows = get_messages_by_ids(self.db_path, hit_ids)

            from collections import defaultdict

            sessions: dict[str, list[dict]] = defaultdict(list)
            for row in rows:
                sessions[row["session_id"]].append(row)

            blocks = []
            for sess_rows in sessions.values():
                ts = sess_rows[0]["created_at"][:16].replace("T", " ")
                lines = [f"({ts})"]
                for row in sess_rows:
                    role_label = "User" if row["role"] == "user" else "Assistant"
                    lines.append(f"{role_label}: {row['content']}")
                blocks.append("\n".join(lines))

            return "\n\n".join(blocks)
        except Exception as exc:
            logger.warning("get_long_term_context failed: %s", exc)
            return ""
