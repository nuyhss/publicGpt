"""
Chat-only request handling.

This version intentionally removes document-upload and retrieval behavior so the
project can focus on a clean public-chatbot experience.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import OLLAMA_MODEL
from app.core.llm import call_ollama, get_response_text
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
    "날씨",
    "뉴스",
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
) -> str:
    parts = [f"[System]\n{system_prompt or DEFAULT_SYSTEM_PROMPT}"]

    history_text = _format_history(history)
    if history_text:
        parts.append(f"[Conversation history]\n{history_text}")

    if web_context:
        parts.append(f"[Web search results]\n{web_context}")

    parts.append(f"[User message]\n{user_message}")
    return "\n\n".join(parts)


def _strip_markdown_emphasis(text: str) -> str:
    if not text:
        return text
    return text.replace("**", "").replace("__", "").strip()


def handle_chat(
    user_message: str,
    history: Optional[List[Message]] = None,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    web_search_enabled: bool = True,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Handle a plain chat request.

    `user_id` is kept in the signature for forward compatibility with upcoming
    chat-memory work, even though it is not used yet.
    """

    del user_id

    history = history or []
    selected_model = model or OLLAMA_MODEL
    web_context = ""

    if web_search_enabled and _might_need_web_search(user_message):
        try:
            web_context = format_search_results(search_web(user_message, max_results=3))
        except Exception as exc:
            logger.debug("Web search skipped after failure: %s", exc)

    prompt = _build_prompt(
        user_message=user_message,
        history=history,
        web_context=web_context,
        system_prompt=system_prompt,
    )

    result = call_ollama(prompt, model=selected_model)
    answer = _strip_markdown_emphasis(get_response_text(result))

    return {
        "answer": answer,
        "mode": "web_search" if web_context else "general",
        "sources": [],
    }
