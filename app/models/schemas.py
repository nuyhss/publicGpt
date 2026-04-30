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
    chat_id: Optional[str] = None


class ChatResponse(BaseModel):
    model: str
    answer: str
    mode: str
    done: bool = True
    memories_used: int = 0


class MemoryCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    user_id: Optional[str] = None
    importance: int = Field(default=1, ge=1, le=5)


class MemoryResponse(BaseModel):
    id: int
    user_id: str
    content: str
    importance: int
    source_message_id: Optional[int] = None
    created_at: str
    updated_at: str


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
