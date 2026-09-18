"""
Kora Agent — Application Settings

All configuration is driven by environment variables (or a .env file).
No secrets or environment-specific values are hardcoded here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="KORA_",
        case_sensitive=False,
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "Kora Agent"
    app_env: Literal["development", "production"] = "development"
    debug: bool = False

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 8765
    workers: int = 1

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://kora:kora_dev_password@localhost:5432/kora",
        description="Async SQLAlchemy-compatible PostgreSQL DSN",
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 86_400  # 24 h

    # ── HuggingFace ───────────────────────────────────────────────────────────
    huggingface_api_token: str = Field(
        default="",
        description="HuggingFace API token (required for Inference API)",
    )
    huggingface_base_url: str = "https://api-inference.huggingface.co"

    # ── Model Registry ────────────────────────────────────────────────────────
    model_registry_path: Path = Path(__file__).parent.parent / "models" / "registry.yaml"

    # ── RAG ───────────────────────────────────────────────────────────────────
    rag_chunk_size_tokens: int = 512
    rag_chunk_overlap_tokens: int = 64
    rag_retrieval_top_k_dense: int = 60
    rag_retrieval_top_k_sparse: int = 60
    rag_rrf_candidates: int = 80
    rag_reranker_top_k: int = 8
    rag_embedding_batch_size: int = 32

    # ── Web Research ──────────────────────────────────────────────────────────
    tavily_api_key: str = Field(default="", description="Tavily API key")
    web_search_max_results: int = 10

    # ── Observability ─────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # ── Permissions ───────────────────────────────────────────────────────────
    # Tools that require explicit user approval before execution
    require_approval_for: list[str] = Field(
        default=["file_write", "shell_exec", "browser_navigate"],
        description="Tool names that require runtime permission grant",
    )

    @field_validator("model_registry_path", mode="before")
    @classmethod
    def resolve_registry_path(cls, v: str | Path) -> Path:
        return Path(v).resolve()


# Singleton — import this everywhere
settings = Settings()
