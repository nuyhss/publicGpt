"""
Chat request handling for the OpenAI-backed chatbot base.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.config import CHAT_HISTORY_MAX_MESSAGES, DEFAULT_MODEL
from app.core.database import list_memories
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


def _format_history(history: List[Message]) -> str:
    if not history:
        return ""

    trimmed = history[-CHAT_HISTORY_MAX_MESSAGES:] if CHAT_HISTORY_MAX_MESSAGES > 0 else history
    return "\n\n".join(f"[{item.role}]\n{item.content}" for item in trimmed)


def _build_prompt(
    user_message: str,
    history: List[Message],
    memory_context: str = "",
    web_context: str = "",
    system_prompt: Optional[str] = None,
) -> str:
    parts = [f"[System]\n{system_prompt or DEFAULT_SYSTEM_PROMPT}"]

    history_text = _format_history(history)
    if history_text:
        parts.append(f"[Conversation history]\n{history_text}")

    if memory_context:
        parts.append(f"[Long-term memory]\n{memory_context}")

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
    Handle a plain chat request with optional long-term memory context.
    """

    history = history or []
    selected_model = model or DEFAULT_MODEL
    web_context = ""
    memories = list_memories(user_id=user_id, limit=12)
    memory_context = "\n".join(f"- {item['content']}" for item in memories)

    if web_search_enabled:
        try:
            web_context = format_search_results(search_web(user_message, max_results=3))
        except Exception as exc:
            logger.debug("Web search failed and was skipped: %s", exc)

    prompt = _build_prompt(
        user_message=user_message,
        history=history,
        memory_context=memory_context,
        web_context=web_context,
        system_prompt=system_prompt,
    )

    result = call_llm(prompt, model=selected_model)
    answer = _strip_markdown_emphasis(get_response_text(result))

    return {
        "answer": answer,
        "mode": "web_search" if web_context else "general",
        "sources": [],
        "memories_used": len(memories),
    }
