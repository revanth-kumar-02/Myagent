from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Cocoa Agent Core"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://localhost:5173",
    ]

    # Database Settings (PostgreSQL preferred, sqlite async fallback for local dev without postgres)
    POSTGRES_USER: str = "cocoa"
    POSTGRES_PASSWORD: str = "cocoa_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "cocoa_db"
    
    # Fallback SQLite DB path if Postgres is unavailable
    SQLITE_DB_PATH: str = "cocoa.db"
    USE_SQLITE_FALLBACK: bool = True

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Default LLM Provider Settings
    LLM_PROVIDER: str = "groq"  # groq | openai | gemini | ollama
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_API_KEY: Optional[str] = None

    # Web Search Engine Keys (Server-side only)
    TAVILY_API_KEY: Optional[str] = None
    BRAVE_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def sqlite_dsn(self) -> str:
        return f"sqlite+aiosqlite:///{self.SQLITE_DB_PATH}"

    @property
    def postgres_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def database_url(self) -> str:
        """Returns the PostgreSQL async SQLAlchemy URL if available, else SQLite fallback."""
        if not self.USE_SQLITE_FALLBACK:
            return self.postgres_dsn
        return self.sqlite_dsn

settings = Settings()
