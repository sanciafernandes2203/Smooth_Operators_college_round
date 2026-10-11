"""
Application configuration using Pydantic Settings.
Loads environment variables from .env file.
"""
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # LLM Provider Configuration
    # -------------------------------------------------------------------------
    llm_provider: Optional[str] = Field(
        default=None,
        description="LLM provider: 'openai', 'anthropic', or 'gemini'",
    )
    llm_api_key: Optional[str] = Field(
        default=None,
        description="API key for the selected LLM provider",
    )
    llm_model: Optional[str] = Field(
        default=None,
        description="Model name for the selected LLM provider",
    )

    # -------------------------------------------------------------------------
    # Database (Supabase PostgreSQL)
    # -------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql://postgres:password@localhost:5432/postgres",
        description="Direct PostgreSQL connection string",
    )

    # -------------------------------------------------------------------------
    # Supabase Storage (optional)
    # -------------------------------------------------------------------------
    supabase_url: Optional[str] = Field(
        default=None,
        description="Supabase project URL",
    )
    supabase_service_role_key: Optional[str] = Field(
        default=None,
        description="Supabase service role key (server-side only)",
    )
    supabase_storage_bucket: Optional[str] = Field(
        default=None,
        description="Supabase storage bucket for source documents",
    )

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    frontend_origin: str = Field(
        default="http://localhost:5173",
        description="Frontend origin for CORS",
    )
    max_upload_size_mb: int = Field(
        default=15,
        description="Maximum upload size in megabytes",
        ge=1,
        le=100,
    )
    backend_host: str = Field(
        default="0.0.0.0",
        description="Backend server bind host",
    )
    backend_port: int = Field(
        default=8000,
        description="Backend server port",
        ge=1,
        le=65535,
    )
    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG, INFO, WARNING, ERROR",
    )

    # -------------------------------------------------------------------------
    # OCR Configuration
    # -------------------------------------------------------------------------
    tesseract_cmd: Optional[str] = Field(
        default=None,
        description="Path to Tesseract executable (if not in PATH)",
    )

    @property
    def max_upload_size_bytes(self) -> int:
        """Maximum upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def has_llm_config(self) -> bool:
        """Check if LLM provider is configured."""
        return all([self.llm_provider, self.llm_api_key, self.llm_model])

    @property
    def has_supabase_storage_config(self) -> bool:
        """Check if Supabase Storage is configured."""
        return all([self.supabase_url, self.supabase_service_role_key, self.supabase_storage_bucket])


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Using lru_cache ensures we only parse .env once.
    """
    return Settings()