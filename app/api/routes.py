"""
Core API routes for the slimmed-down chat-only app.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Optional

from fastapi import APIRouter, Body, File, HTTPException, UploadFile

from app.chat.handlers import handle_chat
from app.config import AVAILABLE_MODELS, DATA_DIR, DEFAULT_MODEL, OCR_MAX_FILE_SIZE
from app.core.ocr import extract_ocr_text
from app.core.llm import check_llm_health
from app.models.schemas import ChatRequest, ChatResponse

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
async def chat(req: ChatRequest):
    try:
        result = await handle_chat(
            user_message=req.message,
            history=req.history,
            model=req.model or DEFAULT_MODEL,
            system_prompt=req.system_prompt,
            web_search_enabled=req.web_search_enabled,
            user_id=req.user_id,
            session_id=req.session_id or req.conversation_id,
            conversation_id=req.conversation_id,
            attachment_text=req.attachment_text,
            attachment_name=req.attachment_name,
        )
        return ChatResponse(
            model=req.model or DEFAULT_MODEL,
            answer=result["answer"],
            mode=result.get("mode", "general"),
            done=True,
            session_id=result.get("session_id"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=f"Chat failed: {exc}")


@router.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(image_bytes) > OCR_MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Image file is too large.")

    try:
        text = await extract_ocr_text(image_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("OCR failed")
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}")

    return {
        "filename": file.filename or "",
        "text": text,
    }
