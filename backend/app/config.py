import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Newtonite Operations Under Pressure"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "super-secret-newtonite-challenge-key-2026-production-ready"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./newtonite_ops.db"

    # Async Outbox Worker
    OUTBOX_POLL_INTERVAL_SECONDS: float = 2.0
    OUTBOX_MAX_RETRIES: int = 3

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
