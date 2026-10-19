"""Application settings and database configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    postgres_user: str = "dentacall"
    postgres_password: str = "dentacall_password"
    postgres_db: str = "dentacall"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    database_url: str = Field(
        default="postgresql+asyncpg://dentacall:dentacall_password@localhost:5432/dentacall"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://dentacall:dentacall_password@localhost:5432/dentacall"
    )

    # Security & API
    api_key: str = "dev_secret_internal_api_key_replace_in_prod"
    rate_limit_per_minute: int = 120

    # Clinic Defaults
    clinic_timezone: str = "Europe/Dublin"
    clinic_name: str = "Grand Canal Dental Clinic"
    clinic_phone: str = "+35312345678"
    clinic_emergency_phone: str = "+35312349999"
    cancellation_notice_hours: int = 24
    slot_hold_duration_seconds: int = 120  # 2 minutes

    # LLM Settings
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    default_llm_provider: str = "openai"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    api_base_url: str = "http://localhost:8000"


settings = Settings()
