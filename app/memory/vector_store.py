"""
ChromaDB storage for conversation embeddings.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("publicgpt.memory.vector")


def get_collection(chroma_path: Path):
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    ef = SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )
    return client.get_or_create_collection(
        name="chat_memories",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def add_message(
    collection,
    message_id: str,
    content: str,
    user_id: str,
    created_at: str,
) -> None:
    collection.add(
        ids=[message_id],
        documents=[content],
        metadatas=[{"user_id": user_id, "created_at": created_at}],
    )


def search_similar(
    collection,
    query: str,
    user_id: str,
    exclude_ids: list[str] | None = None,
) -> list[dict]:
    try:
        total_count = max(1, int(collection.count()))
        results = collection.query(
            query_texts=[query],
            n_results=total_count,
            where={"user_id": user_id},
        )
    except Exception:
        return []

    exclude = set(exclude_ids or [])
    output = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for mid, doc, meta, dist in zip(ids, docs, metas, distances):
        if mid in exclude:
            continue
        output.append(
            {
                "id": mid,
                "content": doc,
                "created_at": meta.get("created_at", ""),
                "distance": dist,
            }
        )

    return output
