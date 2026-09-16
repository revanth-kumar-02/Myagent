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

    # Database Settings (PostgreSQL preferred)
    POSTGRES_USER: str = "cocoa_user"
    POSTGRES_PASSWORD: str = "cocoa_password"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "cocoa"
    
    # Fallback SQLite DB path if Postgres is unavailable
    SQLITE_DB_PATH: str = "cocoa.db"
    USE_SQLITE_FALLBACK: bool = False

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Default LLM Provider Settings (Hugging Face primary)
    LLM_PROVIDER: str = "huggingface"
    HF_TOKEN: Optional[str] = None
    HF_PROVIDER: str = "huggingface"
    HF_CHAT_MODEL: str = "meta-llama/Llama-3.3-70B-Instruct"
    HF_REASONING_MODEL: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B"
    HF_CODING_MODEL: str = "Qwen/Qwen2.5-Coder-32B-Instruct"
    HF_VISION_MODEL: str = "meta-llama/Llama-3.2-11B-Vision-Instruct"
    HF_STT_MODEL: str = "openai/whisper-large-v3"
    HF_TTS_MODEL: str = "facebook/mms-tts-eng"

    # Legacy fallback fields
    LLM_MODEL: str = "meta-llama/Llama-3.3-70B-Instruct"
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
