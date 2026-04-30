"""
Request and response schemas for the chat-only API.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    system_prompt: Optional[str] = (
        "You are PublicGPT, a helpful AI assistant. "
        "Reply in the same language as the user."
    )
    history: List[Message] = Field(default_factory=list)
    model: Optional[str] = None
    web_search_enabled: bool = True
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    attachment_text: Optional[str] = None
    attachment_name: Optional[str] = None


class ChatResponse(BaseModel):
    model: str
    answer: str
    mode: str
    done: bool = True
    session_id: Optional[str] = None


class WebSearchRequest(BaseModel):
    query: str
    max_results: int = Field(default=5, ge=1, le=10)
    region: str = "kr-kr"


class OpenAIMessage(BaseModel):
    role: str
    content: str


class OpenAIChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[OpenAIMessage]
    temperature: Optional[float] = 0.2
    stream: Optional[bool] = False
