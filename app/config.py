"""
Centralized configuration for the slim chat-only app.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
STATIC_DIR = BASE_DIR / "static"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/api")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
AVAILABLE_MODELS = os.getenv(
    "AVAILABLE_MODELS",
    "qwen2.5:7b,llama3.1:latest,llama3.2:latest",
).split(",")

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "180"))
LLM_REPEAT_PENALTY = float(os.getenv("LLM_REPEAT_PENALTY", "1.15"))
LLM_REPEAT_LAST_N = int(os.getenv("LLM_REPEAT_LAST_N", "128"))
LLM_MAX_CONCURRENT_REQUESTS = max(1, int(os.getenv("LLM_MAX_CONCURRENT_REQUESTS", "1")))
LLM_QUEUE_TIMEOUT = int(os.getenv("LLM_QUEUE_TIMEOUT", "240"))

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
