"""Strict Pydantic request and response schemas for all 9 voice receptionist tools."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar

from dentacall_api.utils.phone import normalize_phone_number
from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class ToolResult(BaseModel, Generic[T]):
    """Standardized result envelope returned by all DentaCall tool APIs."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    success: bool = Field(description="True if the tool executed successfully, False otherwise")
    data: T | None = Field(default=None, description="Structured result data on success")
    error_code: str | None = Field(
        default=None, description="Machine-readable error code on failure"
    )
    error_message: str | None = Field(default=None, description="Human-readable error description")
    hint: str | None = Field(
        default=None, description="Plain language instruction for the LLM on how to proceed or fix"
    )


# 1. find_patient
class FindPatientRequest(BaseModel):
    """Input parameters for looking up an existing patient record."""

    phone: str | None = Field(
        default=None, description="Patient contact telephone (will be normalized to Irish E.164)"
    )
    first_name: str | None = Field(default=None, description="Patient first name")
    last_name: str | None = Field(default=None, description="Patient last name")
    date_of_birth: date | None = Field(
        default=None, description="Patient date of birth in YYYY-MM-DD format"
    )

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        if v:
            return str(normalize_phone_number(v))
        return v


class PatientSummary(BaseModel):
    patient_id: uuid.UUID
    first_name: str
    last_name: str
    phone: str
    email: str
    date_of_birth: date


class FindPatientData(BaseModel):
    patients: list[PatientSummary]
    total_found: int


# 2. check_availability
class CheckAvailabilityRequest(BaseModel):
    """Input parameters for finding free appointment slots."""

    start_date: date = Field(description="Search window start date (YYYY-MM-DD)")
    end_date: date = Field(description="Search window end date (YYYY-MM-DD)")
    service_code: str = Field(
        description="Standard service code: CHECKUP, HYGIENE, FILLING, EMERGENCY, EXTRACTION, ROOT_CANAL"
    )
    dentist_id: uuid.UUID | None = Field(
        default=None, description="Optional dentist UUID to filter by specific practitioner"
    )
    dentist_name: str | None = Field(
        default=None, description="Optional dentist name (e.g. 'Dr. Sean', 'Dr. Aoife')"
    )


class SlotSummary(BaseModel):
    dentist_id: uuid.UUID
    dentist_name: str
    service_code: str
    start_time_local: str
    start_time_utc: datetime
    end_time_local: str
    clinical_duration_minutes: int
    buffer_minutes: int


class CheckAvailabilityData(BaseModel):
    service_code: str
    service_name: str
    price_eur: Decimal
    slots: list[SlotSummary]
    total_slots_available: int


# 3. hold_slot
class HoldSlotRequest(BaseModel):
    """Input parameters to temporarily hold a slot for 2 minutes while caller confirms."""

    dentist_id: uuid.UUID = Field(description="Dentist UUID")
    service_code: str = Field(description="Service code (e.g. CHECKUP)")
    start_time_utc: datetime = Field(description="Slot start time in ISO UTC format")
    patient_id: uuid.UUID | str | None = Field(
        default=None, description="Optional patient UUID if already known"
    )


class HoldSlotData(BaseModel):
    hold_id: uuid.UUID
    dentist_id: uuid.UUID
    service_code: str
    start_time_local: str
    start_time_utc: datetime
    held_until_utc: datetime
    hold_duration_seconds: int = 120


# 4. book_appointment
class BookAppointmentRequest(BaseModel):
    """Input parameters to commit and confirm an appointment."""

    patient_id: uuid.UUID | str | None = Field(
        default=None,
        description="Verified patient UUID if existing patient, or null/omitted for new patients",
    )
    patient_name: str | None = Field(
        default=None, description="Caller's full name (used to register new patients)"
    )
    patient_phone: str | None = Field(
        default=None, description="Caller's phone number (used to register new patients)"
    )
    patient_dob: date | None = Field(
        default=None, description="Caller's date of birth (YYYY-MM-DD)"
    )
    dentist_id: uuid.UUID = Field(description="Dentist UUID")
    service_code: str = Field(description="Service code (e.g. CHECKUP)")
    start_time_utc: datetime = Field(description="Confirmed start time in ISO UTC format")
    hold_id: uuid.UUID | None = Field(
        default=None, description="Optional hold UUID acquired during hold_slot"
    )
    notes: str | None = Field(
        default=None, description="Optional caller notes or medical symptoms described"
    )


class BookAppointmentData(BaseModel):
    appointment_id: uuid.UUID
    patient_id: uuid.UUID
    dentist_name: str
    service_name: str
    price_eur: Decimal
    start_time_local: str
    start_time_utc: datetime
    end_time_local: str
    status: str
    clinic_phone: str


# 5. reschedule_appointment
class RescheduleAppointmentRequest(BaseModel):
    """Input parameters to move an existing appointment to a new date/time."""

    appointment_id: uuid.UUID = Field(description="Existing confirmed appointment UUID")
    new_dentist_id: uuid.UUID = Field(description="New dentist UUID")
    new_start_time_utc: datetime = Field(description="New slot start time in ISO UTC format")


class RescheduleAppointmentData(BaseModel):
    new_appointment_id: uuid.UUID
    old_appointment_id: uuid.UUID
    dentist_name: str
    service_name: str
    start_time_local: str
    start_time_utc: datetime
    is_late_reschedule: bool
    policy_notice: str


# 6. cancel_appointment
class CancelAppointmentRequest(BaseModel):
    """Input parameters to cancel an appointment."""

    appointment_id: uuid.UUID = Field(description="Existing appointment UUID to cancel")
    reason: str | None = Field(
        default=None, description="Reason provided by caller for cancellation"
    )


class CancelAppointmentData(BaseModel):
    appointment_id: uuid.UUID
    status: str
    is_late_cancellation: bool
    policy_fee_incurred_eur: Decimal
    policy_notice: str


# 7. get_clinic_info
class DentistInfo(BaseModel):
    dentist_id: uuid.UUID
    name: str
    specialisms: str
    working_days: list[str]


class ServiceInfo(BaseModel):
    code: str
    name: str
    duration_minutes: int
    buffer_minutes: int
    price_eur: Decimal
    description: str


class ClinicInfoData(BaseModel):
    clinic_name: str
    address: str
    phone: str
    emergency_phone: str
    timezone: str
    opening_hours: dict[str, str]
    dentists: list[DentistInfo]
    services: list[ServiceInfo]
    cancellation_policy: str
    emergency_policy: str


# 8. take_message
class TakeMessageRequest(BaseModel):
    """Input parameters when a caller wishes to leave a callback message."""

    caller_name: str = Field(description="Caller full name")
    caller_phone: str = Field(description="Caller contact telephone")
    message: str = Field(description="Message content or inquiry details")
    urgency: str = Field(
        default="NORMAL",
        description="'NORMAL' for general inquiries, 'URGENT' for acute pain/concerns",
    )

    @field_validator("caller_phone")
    @classmethod
    def normalize_caller_phone(cls, v: str) -> str:
        return str(normalize_phone_number(v))


class TakeMessageData(BaseModel):
    message_id: uuid.UUID
    status: str = "LOGGED"
    callback_promise: str


# 9. transfer_to_human
class TransferToHumanRequest(BaseModel):
    """Input parameters to escalate or transfer call to clinic staff or emergency line."""

    caller_phone: str = Field(description="Caller phone number")
    reason: str = Field(
        description="Escalation trigger: 'EMERGENCY_MEDICAL', 'CALLER_REQUEST', or 'COMPLEX_QUERY'"
    )
    patient_id: uuid.UUID | None = Field(default=None, description="Patient UUID if identified")

    @field_validator("caller_phone")
    @classmethod
    def normalize_transfer_phone(cls, v: str) -> str:
        return str(normalize_phone_number(v))


class TransferToHumanData(BaseModel):
    target_phone: str
    reason: str
    spoken_notice_for_caller: str
