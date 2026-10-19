"""Core configuration and clinic metadata models."""

from pydantic import BaseModel, Field


class ClinicConfig(BaseModel):
    """Configuration model for dental clinic settings."""

    name: str = Field(default="Grand Canal Dental Clinic", description="Clinic trade name")
    timezone: str = Field(default="Europe/Dublin", description="IANA timezone name")
    phone: str = Field(default="+35312345678", description="Main clinic telephone in E.164")
    emergency_phone: str = Field(default="+35312349999", description="Emergency triage phone")
    cancellation_notice_hours: int = Field(
        default=24, description="Minimum notice required to cancel without penalty"
    )
