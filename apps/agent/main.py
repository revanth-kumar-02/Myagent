"""
Kora Agent — Application Entry Point

Starts the FastAPI + uvicorn server. Handles startup and shutdown lifecycle.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.http import router as http_router
from api.vision import router as vision_router
from api.ws import router as ws_router
from config import settings
from db.client import shutdown as db_shutdown, startup as db_startup
from observability import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    configure_logging()
    await db_startup()
    from api.deps import get_automation_engine, get_failover_manager, get_task_storage, get_system_monitor
    from tasks.types import TriggerType

    fm = get_failover_manager()
    await fm.start_background_monitor()

    # Start Real-Time Host System Telemetry Monitor
    monitor = get_system_monitor()
    monitor.start()

    # Start Kora Automation & Scheduling Engine
    engine = get_automation_engine()
    engine.start()

    # Restore active scheduled automations from persistent storage
    try:
        storage = get_task_storage()
        tasks = await storage.list_tasks()
        for t in tasks:
            if t.is_active and t.trigger.trigger_type != TriggerType.MANUAL:
                await engine.schedule_task(t)
    except Exception as e:
        structlog.get_logger(__name__).error("failed_to_restore_automations", error=str(e))

    yield

    monitor.stop()
    engine.shutdown(wait=False)
    fm.stop_background_monitor()
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
    app.include_router(vision_router)
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
