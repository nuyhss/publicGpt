"""
Chat-only request handling.

This version intentionally removes document-upload and retrieval behavior so the
project can focus on a clean public-chatbot experience.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import DEFAULT_MODEL
from app.db.repository import load_messages, save_message
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


def _deduplicate_db_history(db_history: List[Message], history: List[Message]) -> List[Message]:
    if not db_history:
        return []
    seen = {(item.role, item.content) for item in history}
    return [item for item in db_history if (item.role, item.content) not in seen]


def _build_prompt(
    user_message: str,
    long_term_memory: List[Message],
    history: List[Message],
    web_context: str = "",
    system_prompt: Optional[str] = None,
) -> str:
    parts = [f"[System]\n{system_prompt or DEFAULT_SYSTEM_PROMPT}"]

    memory_text = _format_history(long_term_memory, max_turns=40)
    if memory_text:
        parts.append(f"[Long-term memory]\n{memory_text}")

    history_text = _format_history(history)
    if history_text:
        parts.append(f"[Recent conversation]\n{history_text}")

    if web_context:
        parts.append(f"[Web results]\n{web_context}")

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
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    del user_id

    history = history or []
    selected_model = model or DEFAULT_MODEL
    web_context = ""
    db_history: List[Message] = []

    if web_search_enabled and _might_need_web_search(user_message):
        try:
            web_context = format_search_results(search_web(user_message, max_results=3))
        except Exception as exc:
            logger.debug("Web search skipped after failure: %s", exc)

    if conversation_id:
        try:
            db_history = await load_messages(conversation_id, limit=40)
        except Exception as exc:
            logger.warning("Failed to load conversation memory (%s): %s", conversation_id, exc)
            db_history = []

    db_history = _deduplicate_db_history(db_history, history)

    prompt = _build_prompt(
        user_message=user_message,
        long_term_memory=db_history,
        history=history,
        web_context=web_context,
        system_prompt=system_prompt,
    )

    result = call_llm(prompt, model=selected_model)
    answer = _strip_markdown_emphasis(get_response_text(result))

    if conversation_id:
        try:
            await save_message(conversation_id, "user", user_message)
        except Exception as exc:
            logger.warning("Failed to save user message (%s): %s", conversation_id, exc)
        try:
            await save_message(conversation_id, "assistant", answer)
        except Exception as exc:
            logger.warning("Failed to save assistant message (%s): %s", conversation_id, exc)

    return {
        "answer": answer,
        "mode": "web_search" if web_context else "general",
        "sources": [],
    }
