"""SQLAlchemy 2.0 database models for DentaCall domain entities."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from dentacall_core.timezone import now_utc


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy domain models."""

    pass


class AppointmentStatus(str, Enum):
    """Status lifecycle for an appointment."""

    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    RESCHEDULED = "RESCHEDULED"


class SlotHoldStatus(str, Enum):
    """Status lifecycle for a 2-minute temporary slot hold."""

    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    CONVERTED = "CONVERTED"


class Clinic(Base):
    """Dental clinic practice entity."""

    __tablename__ = "clinics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Dublin", nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    emergency_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    cancellation_notice_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

    dentists: Mapped[list["Dentist"]] = relationship(
        "Dentist", back_populates="clinic", cascade="all, delete-orphan"
    )
    services: Mapped[list["Service"]] = relationship(
        "Service", back_populates="clinic", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship("Appointment", back_populates="clinic")
    call_logs: Mapped[list["CallLog"]] = relationship("CallLog", back_populates="clinic")


class Dentist(Base):
    """Registered dental practitioner."""

    __tablename__ = "dentists"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    specialisms: Mapped[str] = mapped_column(String(255), default="General Dentistry")
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="dentists")
    working_hours: Mapped[list["WorkingHours"]] = relationship(
        "WorkingHours", back_populates="dentist", cascade="all, delete-orphan"
    )
    time_offs: Mapped[list["TimeOff"]] = relationship(
        "TimeOff", back_populates="dentist", cascade="all, delete-orphan"
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="dentist"
    )
    slot_holds: Mapped[list["SlotHold"]] = relationship("SlotHold", back_populates="dentist")


class Service(Base):
    """Clinical dental procedure offering with pricing and durations."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    price_eur: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="services")
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="service"
    )


class WorkingHours(Base):
    """Weekly working schedule and break times for a dentist."""

    __tablename__ = "working_hours"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dentist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dentists.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    break_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    break_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_working: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    dentist: Mapped["Dentist"] = relationship("Dentist", back_populates="working_hours")

    __table_args__ = (Index("idx_dentist_day_of_week", "dentist_id", "day_of_week", unique=True),)


class TimeOff(Base):
    """Scheduled doctor absence, annual leave, or clinic closure."""

    __tablename__ = "time_offs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dentist_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("dentists.id"), nullable=True)
    start_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), default="Leave", nullable=False)

    dentist: Mapped["Dentist | None"] = relationship("Dentist", back_populates="time_offs")


class Patient(Base):
    """Dental patient record."""

    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment", back_populates="patient"
    )
    call_logs: Mapped[list["CallLog"]] = relationship("CallLog", back_populates="patient")


class Appointment(Base):
    """Scheduled patient clinical appointment."""

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"), nullable=False)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), nullable=False)
    dentist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dentists.id"), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    start_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clinical_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    buffer_duration_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=AppointmentStatus.CONFIRMED.value, nullable=False
    )
    is_late_cancellation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cancellation_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cancelled_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rescheduled_from_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )

    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="appointments")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="appointments")
    dentist: Mapped["Dentist"] = relationship("Dentist", back_populates="appointments")
    service: Mapped["Service"] = relationship("Service", back_populates="appointments")

    __table_args__ = (
        ExcludeConstraint(
            ("dentist_id", "="),
            (func.tstzrange(start_time_utc, end_time_utc, "[)"), "&&"),
            name="no_overlapping_appointments",
            where=(status != "CANCELLED"),
        ),
        Index("idx_appointment_dentist_time", "dentist_id", "start_time_utc", "end_time_utc"),
        Index("idx_appointment_patient", "patient_id"),
    )


class SlotHold(Base):
    """Ephemeral reservation hold for 2 minutes to prevent race conditions during caller confirmation."""

    __tablename__ = "slot_holds"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dentist_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dentists.id"), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"), nullable=False)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    start_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    held_until_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=SlotHoldStatus.ACTIVE.value, nullable=False
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

    dentist: Mapped["Dentist"] = relationship("Dentist", back_populates="slot_holds")
    service: Mapped["Service"] = relationship("Service")
    patient: Mapped["Patient | None"] = relationship("Patient")

    __table_args__ = (
        Index("idx_slot_hold_dentist_active", "dentist_id", "held_until_utc", "status"),
    )


class CallLog(Base):
    """Inbound voice and web call record."""

    __tablename__ = "call_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clinic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinics.id"), nullable=False)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.id"), nullable=True
    )
    call_sid: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    caller_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), default="INBOUND", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="COMPLETED", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    transcript_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), default=Decimal("0.0000"), nullable=False
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False
    )

    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="call_logs")
    patient: Mapped["Patient | None"] = relationship("Patient", back_populates="call_logs")
    appointment: Mapped["Appointment | None"] = relationship("Appointment")
