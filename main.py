"""
Application entry point for the slim chat-only PublicGPT app.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.openai_compat import router as openai_router
from app.api.routes import router as main_router
from app.api.upload_ui import router as ui_router
from app.db.database import create_tables, init_db_path
from app.config import (
    AVAILABLE_MODELS,
    DATA_DIR,
    DEFAULT_MODEL,
    MEMORY_DB_PATH,
    MEMORY_ENABLED,
    STATIC_DIR,
    logger,
    setup_logging,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db_path(DATA_DIR)
    await create_tables()
    if MEMORY_ENABLED:
        from app.memory.db import init_db

        init_db(MEMORY_DB_PATH)
        logger.info("  Memory DB     : %s", MEMORY_DB_PATH)

    logger.info("=" * 60)
    logger.info("PublicGPT API starting up")
    logger.info("  Provider      : openai")
    logger.info("  Default model : %s", DEFAULT_MODEL)
    logger.info("  Models        : %s", ", ".join(m.strip() for m in AVAILABLE_MODELS))
    logger.info("  Data dir      : %s", DATA_DIR)
    logger.info("  Chat UI       : http://127.0.0.1:8000/ui")
    logger.info("=" * 60)

    yield

    logger.info("PublicGPT API shutting down.")


app = FastAPI(
    title="PublicGPT API",
    version="1.0.0",
    description="Chat-only FastAPI app backed by Ollama or OpenAI.",
    lifespan=lifespan,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(main_router)
app.include_router(openai_router)
app.include_router(ui_router)
