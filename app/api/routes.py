"""
Core API routes for the slimmed-down chat-only app.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Body, HTTPException

from app.chat.handlers import handle_chat
from app.config import AVAILABLE_MODELS, DATABASE_PATH, DATA_DIR, DEFAULT_MODEL
from app.core.database import (
    add_memory,
    add_message,
    delete_memory,
    list_memories,
    list_messages,
    maybe_extract_memory,
    normalize_user_id,
)
from app.core.llm import check_llm_health
from app.models.schemas import ChatRequest, ChatResponse, MemoryCreateRequest, MemoryResponse

logger = logging.getLogger("publicgpt.api")

router = APIRouter()
_ui_state_lock = Lock()


def _normalize_user_id(user_id: Optional[str]) -> Optional[str]:
    if user_id is None:
        return None

    raw = str(user_id).strip()
    if not raw:
        return None

    safe = Path(raw).name.strip()
    if safe in {"", ".", ".."}:
        return None
    return safe


def _ui_chats_state_path(user_id: Optional[str]) -> Path:
    normalized_user_id = _normalize_user_id(user_id)
    state_dir = DATA_DIR / "ui_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    filename = f"chats_{normalized_user_id}.json" if normalized_user_id else "chats_default.json"
    return state_dir / filename


@router.get("/")
def root():
    return {
        "message": "PublicGPT API is running",
        "version": "1.0.0",
        "provider": "openai",
        "model": DEFAULT_MODEL,
        "data_dir": str(DATA_DIR),
        "database": "sqlite",
        "database_path": str(DATABASE_PATH),
    }


@router.get("/health")
def health():
    try:
        llm_status = check_llm_health()
        return {
            "status": "ok",
            "provider": "openai",
            "llm": llm_status["status"],
            "model": DEFAULT_MODEL,
            "available_models": AVAILABLE_MODELS,
            "web_search_provider": "tavily_or_duckduckgo",
            "database": "sqlite",
            "database_path": str(DATABASE_PATH),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Health check failed: {exc}")


@router.get("/models")
def list_models():
    return {
        "provider": "openai",
        "default": DEFAULT_MODEL,
        "available": AVAILABLE_MODELS,
    }


@router.get("/memory")
def get_memory(user_id: Optional[str] = None, limit: int = 20):
    return {
        "user_id": normalize_user_id(user_id),
        "memories": list_memories(user_id=user_id, limit=limit),
    }


@router.post("/memory", response_model=MemoryResponse)
def create_memory(req: MemoryCreateRequest):
    try:
        memory_id = add_memory(
            user_id=req.user_id,
            content=req.content,
            importance=req.importance,
        )
        memories = list_memories(user_id=req.user_id, limit=100)
        for memory in memories:
            if memory["id"] == memory_id:
                return MemoryResponse(**memory)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    raise HTTPException(status_code=500, detail="Failed to create memory.")


@router.delete("/memory/{memory_id}")
def remove_memory(memory_id: int, user_id: Optional[str] = None):
    deleted = delete_memory(user_id=user_id, memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found.")
    return {"deleted": True, "id": memory_id}


@router.get("/messages")
def get_messages(
    user_id: Optional[str] = None,
    chat_id: Optional[str] = None,
    limit: int = 100,
):
    return {
        "user_id": normalize_user_id(user_id),
        "chat_id": chat_id,
        "messages": list_messages(user_id=user_id, chat_id=chat_id, limit=limit),
    }


@router.get("/ui-state/chats")
def get_ui_state_chats(user_id: Optional[str] = None):
    state_path = _ui_chats_state_path(user_id)
    if not state_path.exists():
        return {"chats": {}}

    with _ui_state_lock:
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read UI chat state (%s): %s", state_path, exc)
            return {"chats": {}}

    chats = payload.get("chats") if isinstance(payload, dict) else {}
    return {"chats": chats if isinstance(chats, dict) else {}}


@router.put("/ui-state/chats")
def put_ui_state_chats(payload: dict = Body(...), user_id: Optional[str] = None):
    chats = payload.get("chats") if isinstance(payload, dict) else None
    if not isinstance(chats, dict):
        raise HTTPException(status_code=400, detail="'chats' must be an object.")

    state_path = _ui_chats_state_path(user_id)
    document = {"chats": chats}

    try:
        encoded = json.dumps(document, ensure_ascii=False)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid chats payload: {exc}")

    if len(encoded.encode("utf-8")) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Chat state payload too large.")

    with _ui_state_lock:
        try:
            state_path.write_text(
                json.dumps(document, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.exception("Failed to write UI chat state (%s)", state_path)
            raise HTTPException(status_code=500, detail=f"Failed to save UI chat state: {exc}")

    return {"saved": True, "count": len(chats)}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        selected_model = req.model or DEFAULT_MODEL
        user_message_id = add_message(
            user_id=req.user_id,
            chat_id=req.chat_id,
            role="user",
            content=req.message,
            model=selected_model,
        )
        result = handle_chat(
            user_message=req.message,
            history=req.history,
            model=selected_model,
            system_prompt=req.system_prompt,
            web_search_enabled=req.web_search_enabled,
            user_id=req.user_id,
        )
        add_message(
            user_id=req.user_id,
            chat_id=req.chat_id,
            role="assistant",
            content=result["answer"],
            model=selected_model,
            mode=result.get("mode", "general"),
        )

        memory_content = maybe_extract_memory(req.message)
        if memory_content:
            try:
                add_memory(
                    user_id=req.user_id,
                    content=memory_content,
                    importance=3,
                    source_message_id=user_message_id,
                )
            except ValueError:
                pass

        return ChatResponse(
            model=selected_model,
            answer=result["answer"],
            mode=result.get("mode", "general"),
            done=True,
            memories_used=result.get("memories_used", 0),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}")
