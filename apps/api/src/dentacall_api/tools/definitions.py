"""Matching JSON Schema tool definitions for LLM tool-calling (OpenAI / Claude format)."""

from typing import Any

from dentacall_api.schemas.tools import (
    BookAppointmentRequest,
    CancelAppointmentRequest,
    CheckAvailabilityRequest,
    FindPatientRequest,
    HoldSlotRequest,
    RescheduleAppointmentRequest,
    TakeMessageRequest,
    TransferToHumanRequest,
)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "find_patient",
        "description": "Search for an existing clinic patient record using phone number or name and date of birth.",
        "parameters": FindPatientRequest.model_json_schema(),
    },
    {
        "name": "check_availability",
        "description": "Find open, bookable dental appointment slots for a specific procedure within a date window.",
        "parameters": CheckAvailabilityRequest.model_json_schema(),
    },
    {
        "name": "hold_slot",
        "description": "Temporarily lock a chosen slot for 2 minutes while verifying patient details.",
        "parameters": HoldSlotRequest.model_json_schema(),
    },
    {
        "name": "book_appointment",
        "description": "Confirm and finalize an appointment booking for a patient with a specific dentist.",
        "parameters": BookAppointmentRequest.model_json_schema(),
    },
    {
        "name": "reschedule_appointment",
        "description": "Move an existing appointment to a new date and time with 24-hour notice policy evaluation.",
        "parameters": RescheduleAppointmentRequest.model_json_schema(),
    },
    {
        "name": "cancel_appointment",
        "description": "Cancel an appointment and enforce the 24-hour notice cancellation policy.",
        "parameters": CancelAppointmentRequest.model_json_schema(),
    },
    {
        "name": "get_clinic_info",
        "description": "Retrieve official clinic operating hours, dentist specialties, services, prices, and triage policies.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "take_message",
        "description": "Record a callback request or message from a caller when the clinic is closed or doctors are busy.",
        "parameters": TakeMessageRequest.model_json_schema(),
    },
    {
        "name": "transfer_to_human",
        "description": "Transfer the caller to clinic human reception or the emergency duty dentist line.",
        "parameters": TransferToHumanRequest.model_json_schema(),
    },
]


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return the list of all 9 JSON Schema tool definitions."""
    return TOOL_DEFINITIONS
