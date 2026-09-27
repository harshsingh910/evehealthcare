"""
Application configuration using pydantic-settings.

All secrets and environment-specific values are loaded from environment variables.
Never hardcode secrets in source code.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Application
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")

    # Database — PostgreSQL is used because it provides ACID transactions,
    # UNIQUE constraints for idempotency, and robust row-level locking.
    DATABASE_URL: str = Field(default="postgresql://eve_user:eve_password@localhost:5432/eve_healthcare")

    # Redis — Used as a cache-aside layer and rate limiter, NOT as source of truth.
    # If Redis is unavailable, the app degrades gracefully to direct DB queries.
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # JWT Authentication
    SECRET_KEY: str = Field(default="change-me-to-a-real-secret-key-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    JWT_ALGORITHM: str = Field(default="HS256")

    # Rate Limiting (Redis-based)
    RATE_LIMIT_LOGIN_ATTEMPTS: int = Field(default=5)
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60)
    # Payments get a separate, stricter window to prevent payment flooding/abuse.
    RATE_LIMIT_PAYMENT_ATTEMPTS: int = Field(default=10)
    RATE_LIMIT_PAYMENT_WINDOW_SECONDS: int = Field(default=60)

    # Cache TTL
    CACHE_TTL_SECONDS: int = Field(default=300)

    # Celery — Uses Redis as broker for background task processing.
    # Separate Redis DB (db=1) to isolate task queue from cache.
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/1")

    # Server
    PORT: int = Field(default=8000)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
