import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # API Keys
    GOOGLE_PLACES_API_KEY: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    FLIGHT_API_KEY: Optional[str] = None
    FLIGHT_AFFILIATE_MARKER: Optional[str] = None
    KIE_AI_API_KEY: Optional[str] = None

    # Database
    DATABASE_URL: str = Field("postgresql+asyncpg://user:pass@localhost/travel_db", env="DATABASE_URL")

    # Redis
    REDIS_URL: str = Field("redis://localhost:6379/0", env="REDIS_URL")

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(10, env="RATE_LIMIT_REQUESTS")   # per minute per user
    RATE_LIMIT_PERIOD: int = Field(60, env="RATE_LIMIT_PERIOD")       # seconds

    # Celery
    CELERY_BROKER_URL: str = Field("redis://localhost:6379/1", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field("redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")

    # Video Generation
    INTERNAL_API_BASE: str = Field("http://localhost:8001", env="INTERNAL_API_BASE")  
    VIDEO_MAX_CONCURRENT: int = Field(5, env="VIDEO_MAX_CONCURRENT")
    VIDEO_MAX_DAYS: int = Field(7, env="VIDEO_MAX_DAYS")

    # File cleanup
    UPLOAD_CLEANUP_HOURS: int = Field(1, env="UPLOAD_CLEANUP_HOURS")   # delete photos older than 1h
    UPLOAD_CLEANUP_INTERVAL_HOURS: int = Field(6, env="UPLOAD_CLEANUP_INTERVAL_HOURS")  # run every 6 hours

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()