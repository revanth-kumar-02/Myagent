"""
api.deps — FastAPI Dependency Injection

Provides shared singletons (DB session, Redis, model registry, etc.)
as FastAPI dependencies for WebSocket and HTTP handlers.
"""

from __future__ import annotations

from functools import lru_cache

from collections.abc import AsyncGenerator
from typing import Any

from config import settings
from db.client import AsyncSessionFactory, get_redis
from models.registry import ModelRegistry
from research.router import ResearchRouter
from tools.registry import build_default_registry, ToolRegistry


@lru_cache(maxsize=1)
def get_model_registry() -> ModelRegistry:
    return ModelRegistry.load(settings.model_registry_path)


@lru_cache(maxsize=1)
def get_tool_registry() -> ToolRegistry:
    return build_default_registry()


@lru_cache(maxsize=1)
def get_research_router() -> ResearchRouter:
    return ResearchRouter()


async def get_agent_dependencies() -> AsyncGenerator[dict[str, Any], None]:
    """
    Collects all per-request dependencies for AgentSession construction.
    DB session is created per-request; singletons are cached.
    """
    async with AsyncSessionFactory() as db:
        yield {
            "db": db,
            "redis": get_redis(),
            "model_registry": get_model_registry(),
            "tool_registry": get_tool_registry(),
            "research_router": get_research_router(),
        }

