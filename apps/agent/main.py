"""
Kora Agent — Application Entry Point

Starts the FastAPI + uvicorn server. Handles startup and shutdown lifecycle.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.http import router as http_router
from api.ws import router as ws_router
from config import settings
from db.client import shutdown as db_shutdown, startup as db_startup
from observability import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown lifecycle."""
    configure_logging()
    await db_startup()
    yield
    await db_shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Kora — RAG-first autonomous personal AI agent backend",
        lifespan=lifespan,
    )

    # CORS — only allow the local Flutter desktop client in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else ["http://localhost:*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(http_router)
    app.include_router(ws_router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development",
        workers=settings.workers,
        log_level=settings.log_level.lower(),
    )
