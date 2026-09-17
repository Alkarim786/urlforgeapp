"""Application configuration managed via Pydantic Settings.

Following 12-factor application principles:
Configuration is stored in environment variables, never hard-coded.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application Settings class with strict typing and validation."""

    APP_NAME: str = "URLForge"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    APP_URL: str = "http://localhost:8000"
    SECRET_KEY: str = "insecure-dev-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://urlforge_user:urlforge_password@localhost:5432/urlforge_db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # Redis Cache
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 86400  # 24 hours

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100

    # Short code configuration
    DEFAULT_SHORT_CODE_LENGTH: int = 7
    MAX_COLLISION_RETRIES: int = 5
    DEFAULT_EXPIRY_DAYS: Optional[int] = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance to avoid reloading environment variables on each call."""
    return Settings()
