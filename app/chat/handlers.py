"""
Chat-only request handling.

This version intentionally removes document-upload and retrieval behavior so the
project can focus on a clean public-chatbot experience.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from app.config import DEFAULT_MODEL, MEMORY_CHROMA_PATH, MEMORY_DB_PATH, MEMORY_ENABLED, MEMORY_TOP_K
from app.core.llm import call_llm, get_response_text
from app.core.web_search import format_search_results, search_web
from app.models.schemas import Message

logger = logging.getLogger("publicgpt.chat")

DEFAULT_SYSTEM_PROMPT = (
    "You are PublicGPT, a helpful AI assistant. "
    "Reply in the same language the user is using. "
    "Answer directly, be honest when you are unsure, and do not invent facts. "
    "If web search results are provided, use them only when they are relevant."
)

WEB_SEARCH_HINTS = [
    "today",
    "latest",
    "recent",
    "current",
    "now",
    "news",
    "price",
    "stock",
    "weather",
    "score",
    "live",
    "release date",
    "발표",
    "최신",
    "최근",
    "현재",
    "오늘",
    "뉴스",
    "날씨",
    "주가",
    "가격",
    "실시간",
]


def _format_history(history: List[Message], max_turns: int = 12) -> str:
    if not history:
        return ""
    trimmed = history[-max_turns:]
    return "\n\n".join(f"[{item.role}]\n{item.content}" for item in trimmed)


def _might_need_web_search(text: str) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in WEB_SEARCH_HINTS)


def _build_prompt(
    user_message: str,
    history: List[Message],
    web_context: str = "",
    system_prompt: Optional[str] = None,
    long_term_context: str = "",
    attachment_text: str = "",
    attachment_name: str = "",
) -> str:
    parts = [f"[System]\n{system_prompt or DEFAULT_SYSTEM_PROMPT}"]

    if long_term_context:
        parts.append(f"[과거 대화 기억]\n{long_term_context}")

    history_text = _format_history(history)
    if history_text:
        parts.append(f"[Conversation history]\n{history_text}")

    if attachment_text:
        title = attachment_name or "attached image"
        parts.append(f"[Attached image OCR: {title}]\n{attachment_text}")

    if web_context:
        parts.append(f"[Web search results]\n{web_context}")

    parts.append(f"[User message]\n{user_message}")
    return "\n\n".join(parts)


def _strip_markdown_emphasis(text: str) -> str:
    if not text:
        return text
    return text.replace("**", "").replace("__", "").strip()


async def handle_chat(
    user_message: str,
    history: Optional[List[Message]] = None,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    web_search_enabled: bool = True,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    attachment_text: Optional[str] = None,
    attachment_name: Optional[str] = None,
) -> Dict[str, Any]:
    history = history or []
    selected_model = model or DEFAULT_MODEL
    session_id = session_id or conversation_id or str(uuid.uuid4())
    web_context = ""
    long_term_context = ""

    if web_search_enabled and _might_need_web_search(user_message):
        try:
            web_context = format_search_results(search_web(user_message, max_results=3))
        except Exception as exc:
            logger.debug("Web search skipped after failure: %s", exc)

    if MEMORY_ENABLED and user_id:
        try:
            from app.memory.memory_handler import MemoryHandler

            memory = MemoryHandler(MEMORY_DB_PATH, MEMORY_CHROMA_PATH)
            long_term_context = memory.get_long_term_context(
                user_id=user_id,
                current_session_id=session_id,
                current_message=user_message,
                n_results=MEMORY_TOP_K,
            )
        except Exception as exc:
            logger.warning("Memory retrieval failed: %s", exc)

    prompt = _build_prompt(
        user_message=user_message,
        history=history,
        web_context=web_context,
        system_prompt=system_prompt,
        long_term_context=long_term_context,
        attachment_text=attachment_text or "",
        attachment_name=attachment_name or "",
    )

    result = call_llm(prompt, model=selected_model)
    answer = _strip_markdown_emphasis(get_response_text(result))

    if MEMORY_ENABLED and user_id:
        try:
            from app.memory.memory_handler import MemoryHandler

            memory = MemoryHandler(MEMORY_DB_PATH, MEMORY_CHROMA_PATH)
            memory.save_turn(
                user_id=user_id,
                session_id=session_id,
                user_message=user_message,
                assistant_reply=answer,
            )
        except Exception as exc:
            logger.warning("Memory save failed: %s", exc)

    return {
        "answer": answer,
        "mode": "web_search" if web_context else "general",
        "sources": [],
        "session_id": session_id,
    }
