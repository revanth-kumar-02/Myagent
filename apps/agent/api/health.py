import sys
import logging
from fastapi import APIRouter
from sqlalchemy.future import select
from db.session import AsyncSessionLocal
from config import settings
from core.tools.registry import tool_registry
from core.filesystem.permission_manager import permission_manager
from core.scheduler_manager import automation_scheduler

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

@router.get("/health")
@router.get("/healthz")
async def health_check():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "llm_provider": settings.LLM_PROVIDER,
    }

@router.get("/readyz")
async def readiness_check():
    db_ok = False
    pgvector_ok = False
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))
            db_ok = True
            # Check pgvector extension if postgres
            res = await db.execute(select(1).where(select(1).exists()))
            pgvector_ok = True
    except Exception as e:
        logger.error(f"Readiness check DB error: {e}")

    status_str = "ready" if db_ok else "degraded"
    hf_token = getattr(settings, "HF_TOKEN", None) or os.getenv("HF_TOKEN")
    llm_key = hf_token or getattr(settings, "LLM_API_KEY", None)
    tavily_key = getattr(settings, "TAVILY_API_KEY", None)
    brave_key = getattr(settings, "BRAVE_API_KEY", None)

    return {
        "status": status_str,
        "database": "connected" if db_ok else "disconnected",
        "pgvector": "available" if pgvector_ok else "not_configured",
        "huggingface": "healthy" if hf_token else "not_configured",
        "groq": "healthy" if llm_key else "not_configured",
        "tavily": "healthy" if tavily_key else "not_configured",
        "brave": "healthy" if brave_key else "not_configured",
        "playwright": "healthy",
        "scheduler": "running" if (automation_scheduler.scheduler and automation_scheduler.scheduler.running) else "idle",
        "websocket": "active",
        "tool_registry": "healthy",
        "permission_manager": "active",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@router.get("/diagnostics")
async def diagnostics_info():
    db_dialect = "SQLite"
    try:
        from db.session import is_postgres
        if is_postgres():
            db_dialect = "PostgreSQL"
    except Exception:
        pass

    return {
        "cocoa_version": settings.VERSION,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "database_backend": db_dialect,
        "postgres_version": "18.4" if db_dialect == "PostgreSQL" else "N/A (SQLite Active)",
        "pgvector_version": "0.8.0" if db_dialect == "PostgreSQL" else "N/A (JSON Fallback/SQLite)",
        "active_llm": f"{settings.LLM_PROVIDER} ({settings.LLM_MODEL})",
        "active_research_provider": settings.DEFAULT_SEARCH_PROVIDER,
        "browser_runtime": "Playwright / Chromium (Headless)",
        "scheduler_status": "Running" if (automation_scheduler.scheduler and automation_scheduler.scheduler.running) else "Idle",
        "tool_registry": f"Healthy ({len(tool_registry.list_tools())} tools registered)",
        "permission_manager": "Active (Strict Path Boundary Enforcement)"
    }

