"""
Centralized configuration for the OpenAI-only chat app.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
STATIC_DIR = BASE_DIR / "static"

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
AVAILABLE_MODELS = [
    model.strip()
    for model in os.getenv(
        "OPENAI_AVAILABLE_MODELS",
        "gpt-5.5,gpt-5.4-mini,gpt-4.1-mini",
    ).split(",")
    if model.strip()
]
OPENAI_ORGANIZATION = os.getenv("OPENAI_ORGANIZATION", "").strip()
OPENAI_PROJECT = os.getenv("OPENAI_PROJECT", "").strip()

DEFAULT_MODEL = OPENAI_MODEL

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "180"))
LLM_MAX_CONCURRENT_REQUESTS = max(1, int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", "1")))
LLM_QUEUE_TIMEOUT = int(os.getenv("LLM_QUEUE_TIMEOUT", "240"))
CHAT_HISTORY_MAX_MESSAGES = max(0, int(os.getenv("CHAT_HISTORY_MAX_MESSAGES", "0")))

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
DUCKDUCKGO_MAX_RESULTS = max(1, int(os.getenv("DUCKDUCKGO_MAX_RESULTS", "5")))
DUCKDUCKGO_REGION = os.getenv("DUCKDUCKGO_REGION", "kr-kr")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


logger = logging.getLogger("publicgpt")
