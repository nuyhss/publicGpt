"""
Long-term memory store.

Search strategy priority:
1. Use sentence-transformers when available for vector cosine similarity
2. Fall back to TF-IDF keyword similarity with scikit-learn

Schema
------
messages (
    id          INTEGER PRIMARY KEY,
    session_id  TEXT    NOT NULL,
    user_id     TEXT,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    summary     TEXT,
    embedding   BLOB,
    created_at  TEXT    NOT NULL
)
"""

from __future__ import annotations

import io
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import List, Optional, Tuple

import numpy as np

from app.config import EMBED_MODEL_NAME, MEMORY_DB_PATH

logger = logging.getLogger("publicgpt.memory.store")

_embed_model = None
_embed_lock = Lock()
_db_lock = Lock()
_USE_VECTOR: Optional[bool] = None


def _get_embed_model():
    global _embed_model, _USE_VECTOR
    if _USE_VECTOR is not None:
        return _embed_model
    with _embed_lock:
        if _USE_VECTOR is not None:
            return _embed_model
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model: %s", EMBED_MODEL_NAME)
            _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
            _USE_VECTOR = True
            logger.info("Vector search enabled.")
        except Exception as exc:
            logger.info("sentence-transformers unavailable (%s), using TF-IDF fallback.", exc)
            _embed_model = None
            _USE_VECTOR = False
    return _embed_model


def _embed_vector(text: str) -> Optional[bytes]:
    model = _get_embed_model()
    if model is None:
        return None
    try:
        vec = model.encode(text, normalize_embeddings=True).astype(np.float32)
        buf = io.BytesIO()
        np.save(buf, vec)
        return buf.getvalue()
    except Exception as exc:
        logger.debug("Embedding failed: %s", exc)
        return None


def _load_vec(blob: bytes) -> Optional[np.ndarray]:
    try:
        return np.load(io.BytesIO(blob))
    except Exception:
        return None


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom else 0.0


def _tfidf_search(query: str, rows: list, min_score: float = 0.01) -> List[dict]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    contents = [r["content"] for r in rows]
    if not contents:
        return []

    corpus = contents + [query]
    try:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 3)).fit_transform(corpus)
    except Exception as exc:
        logger.debug("TF-IDF failed: %s", exc)
        return []

    scores = cosine_similarity(vec[-1], vec[:-1])[0]
    scored: List[Tuple[float, dict]] = [
        (
            float(score),
            {
                "role": row["role"],
                "content": row["content"],
                "summary": row["summary"],
                "created_at": row["created_at"],
                "score": round(float(score), 3),
                "search_mode": "tfidf",
            },
        )
        for score, row in zip(scores, rows)
        if float(score) > min_score
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored]


def _conn() -> sqlite3.Connection:
    Path(MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(MEMORY_DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def _db():
    with _db_lock:
        con = _conn()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def init_db() -> None:
    _get_embed_model()
    with _db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT    NOT NULL,
                user_id     TEXT,
                role        TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                summary     TEXT,
                embedding   BLOB,
                created_at  TEXT    NOT NULL
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_user ON messages(user_id)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_created ON messages(created_at)")
    mode = "vector" if _USE_VECTOR else "tfidf"
    logger.info("Memory DB ready: %s (search_mode=%s)", MEMORY_DB_PATH, mode)


def save_message(
    session_id: str,
    role: str,
    content: str,
    user_id: Optional[str] = None,
    summary: Optional[str] = None,
) -> int:
    embedding = _embed_vector(content)
    now = datetime.now(timezone.utc).isoformat()
    with _db() as con:
        cur = con.execute(
            """
            INSERT INTO messages
            (session_id, user_id, role, content, summary, embedding, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, role, content, summary, embedding, now),
        )
        return int(cur.lastrowid)


def search_memory(
    query: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    min_score: float = 0.35,
) -> List[dict]:
    del user_id

    if not session_id:
        return []

    _get_embed_model()

    with _db() as con:
        rows = con.execute(
            """
            SELECT role, content, summary, created_at, embedding
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at DESC
            """,
            (session_id,),
        ).fetchall()

    rows = [dict(row) for row in rows]
    if not rows:
        return []

    if _USE_VECTOR:
        q_vec = _embed_vector(query)
        if q_vec is None:
            return []
        q_arr = np.load(io.BytesIO(q_vec))
        scored: List[Tuple[float, dict]] = []
        for row in rows:
            if not row["embedding"]:
                continue
            vec = _load_vec(row["embedding"])
            if vec is None:
                continue
            score = _cosine(q_arr, vec)
            if score >= min_score:
                scored.append(
                    (
                        score,
                        {
                            "role": row["role"],
                            "content": row["content"],
                            "summary": row["summary"],
                            "created_at": row["created_at"],
                            "score": round(score, 3),
                            "search_mode": "vector",
                        },
                    )
                )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scored]

    return _tfidf_search(query, rows, min_score=min_score)


def get_session_messages(session_id: str) -> List[dict]:
    with _db() as con:
        rows = con.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def update_summary(session_id: str, summary: str) -> None:
    with _db() as con:
        con.execute(
            "UPDATE messages SET summary=? WHERE session_id=?",
            (summary, session_id),
        )
