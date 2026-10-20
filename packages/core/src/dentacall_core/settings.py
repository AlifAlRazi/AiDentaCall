from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Ensure .env in repo root takes precedence over any stale OS environment variables
_root_env = Path(__file__).resolve().parents[4] / ".env"
if _root_env.exists():
    load_dotenv(_root_env, override=True)
else:
    load_dotenv(override=True)


class Settings(BaseSettings):
    """Global settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_root_env) if _root_env.exists() else ".env",
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

    # Voice & Audio Pipeline (Stage 5)
    deepgram_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel / clear female voice
    elevenlabs_model: str = "eleven_turbo_v2_5"
    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None

    # Telephony & Twilio (Stage 6)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    livekit_sip_uri: str | None = None
    emergency_transfer_number: str = "+35312349999"
    clinic_escalation_number: str = "+35312345679"
    max_concurrent_calls: int = 10
    daily_spend_cap_usd: float = 25.0
    call_recording_notice_enabled: bool = True

    # Observability & Cost Tracking (Stage 7)
    otel_service_name: str = "dentacall-voice"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    data_retention_days: int = 90
    log_format: str = "json"


settings = Settings()
