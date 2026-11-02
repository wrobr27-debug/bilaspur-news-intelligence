import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict, validator


def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URL for SQLAlchemy Psycopg 3 compatibility.

    Converts postgresql:// URLs to postgresql+psycopg:// URLs.
    Preserves existing query parameters (like sslmode=require for Neon).
    """
    if url.startswith("postgresql://") and "+psycopg" not in url:
        # Replace postgresql:// with postgresql+psycopg://
        normalized = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return normalized
    return url


class Settings(BaseSettings):
    """Configuration settings for Bilaspur News Intelligence."""

    # Database
    database_url: str = Field(
        default="sqlite:///./data/bilaspur_news.db",
        alias="DATABASE_URL",
    )

    # YouTube API
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")

    # Collection settings
    collection_timezone: str = Field(default="Asia/Kolkata", alias="COLLECTION_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Optional: OpenCode API key for LLM processing (Stage 2+)
    opencode_api_key: str = Field(default="", alias="OPENCODE_API_KEY")

    # GitHub deployment
    github_pages_token: str = Field(default="", alias="GITHUB_PAGES_TOKEN")

    # Collection intervals (minutes) - defaults
    default_collection_interval: int = Field(default=60, alias="DEFAULT_COLLECTION_INTERVAL")
    government_interval: int = Field(default=30, alias="GOVERNMENT_INTERVAL")
    newspaper_interval: int = Field(default=30, alias="NEWSPAPER_INTERVAL")
    youtube_interval: int = Field(default=60, alias="YOUTUBE_INTERVAL")
    lower_priority_interval: int = Field(default=120, alias="LOWER_PRIORITY_INTERVAL")

    # HTTP timeout settings
    http_timeout_seconds: int = Field(default=30, alias="HTTP_TIMEOUT")
    http_connect_timeout: int = Field(default=10, alias="HTTP_CONNECT_TIMEOUT")

    # Retry settings
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    backoff_factor: float = Field(default=2.0, alias="BACKOFF_FACTOR")

    @validator("database_url", pre=True)
    def normalize_database_url(cls, v):
        return normalize_database_url(v)

    class Config:
        env_prefix = "BILASUR_"
        env_file = ".env"
        case_sensitive = False


settings = Settings()