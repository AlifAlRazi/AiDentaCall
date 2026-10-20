"""LiveKit tool adapters for DentaCall clinical reception actions."""

import json
import logging
import uuid
from typing import Any

from livekit.agents import llm

from dentacall_agent.tools import AgentToolDispatcher

logger = logging.getLogger(__name__)


def create_livekit_tools(
    dispatcher: AgentToolDispatcher | None = None,
    call_id: str | None = None,
) -> list[llm.FunctionTool]:
    """Create all 9 receptionist tools decorated as LiveKit FunctionTools."""
    tool_disp = dispatcher or AgentToolDispatcher()
    active_call_id = call_id or str(uuid.uuid4())

    @llm.function_tool(
        name="find_patient",
        description="Search for an existing patient record in clinic database by phone number or name and date of birth.",
    )
    async def find_patient(
        phone: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        date_of_birth: str | None = None,
    ) -> str:
        """Find an existing patient record in the database."""
        args: dict[str, Any] = {}
        if phone:
            args["phone"] = phone
        if first_name:
            args["first_name"] = first_name
        if last_name:
            args["last_name"] = last_name
        if date_of_birth:
            args["date_of_birth"] = date_of_birth

        result = await tool_disp.execute_tool("find_patient", args, call_id=active_call_id)
        return json.dumps(result)

    @llm.function_tool(
        name="check_availability",
        description="Search for open appointment slots for a specific dental procedure within a date range.",
    )
    async def check_availability(
        service_code: str,
        start_date: str,
        end_date: str,
        dentist_name: str | None = None,
    ) -> str:
        """Check open available slots for a procedure within a date window."""
        args: dict[str, Any] = {
            "service_code": service_code.upper().strip(),
            "start_date": start_date,
            "end_date": end_date,
        }
        if dentist_name:
            args["dentist_name"] = dentist_name

        result = await tool_disp.execute_tool("check_availability", args, call_id=active_call_id)
        return json.dumps(result)

    @llm.function_tool(
        name="hold_slot",
        description="Temporarily lock a chosen slot for 2 minutes while verifying caller identity and details.",
    )
    async def hold_slot(
        dentist_id: str,
        service_code: str,
        start_time_utc: str,
        patient_id: str | None = None,
    ) -> str:
        """Temporarily hold a slot for 2 minutes."""
        args: dict[str, Any] = {
            "dentist_id": dentist_id,
            "service_code": service_code.upper().strip(),
            "start_time_utc": start_time_utc,
        }
        if patient_id:
            args["patient_id"] = patient_id

        result = await tool_disp.execute_tool("hold_slot", args, call_id=active_call_id)
        if result.get("success") and result.get("data", {}).get("hold_id"):
            from dentacall_core.telephony import telephony_manager

            telephony_manager.register_call_hold(active_call_id, result["data"]["hold_id"])
        return json.dumps(result)

    @llm.function_tool(
        name="book_appointment",
        description="Confirm and finalize an appointment booking. ONLY call AFTER reading details back and receiving explicit confirmation.",
    )
    async def book_appointment(
        dentist_id: str,
        service_code: str,
        start_time_utc: str,
        patient_id: str | None = None,
        patient_name: str | None = None,
        patient_phone: str | None = None,
        patient_dob: str | None = None,
        hold_id: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Confirm and finalize a dental appointment booking."""
        args: dict[str, Any] = {
            "dentist_id": dentist_id,
            "service_code": service_code.upper().strip(),
            "start_time_utc": start_time_utc,
        }
        if patient_id:
            args["patient_id"] = patient_id
        if patient_name:
            args["patient_name"] = patient_name
        if patient_phone:
            args["patient_phone"] = patient_phone
        if patient_dob:
            args["patient_dob"] = patient_dob
        if hold_id:
            args["hold_id"] = hold_id
        if notes:
            args["notes"] = notes

        result = await tool_disp.execute_tool("book_appointment", args, call_id=active_call_id)
        if result.get("success") and hold_id:
            from dentacall_core.telephony import telephony_manager

            telephony_manager.mark_hold_booked(active_call_id, hold_id)
        return json.dumps(result)

    @llm.function_tool(
        name="reschedule_appointment",
        description="Move an existing appointment to a new date and time. Must inform caller of 24-hour notice policy before calling.",
    )
    async def reschedule_appointment(
        appointment_id: str,
        new_start_time_utc: str,
        hold_id: str | None = None,
        reason: str | None = None,
    ) -> str:
        """Reschedule an existing appointment."""
        args: dict[str, Any] = {
            "appointment_id": appointment_id,
            "new_start_time_utc": new_start_time_utc,
        }
        if hold_id:
            args["hold_id"] = hold_id
        if reason:
            args["reason"] = reason

        result = await tool_disp.execute_tool("reschedule_appointment", args)
        return json.dumps(result)

    @llm.function_tool(
        name="cancel_appointment",
        description="Cancel an appointment in clinic calendar. Must inform caller of 24-hour notice policy before calling.",
    )
    async def cancel_appointment(
        appointment_id: str,
        reason: str | None = None,
    ) -> str:
        """Cancel an existing appointment."""
        args: dict[str, Any] = {"appointment_id": appointment_id}
        if reason:
            args["reason"] = reason

        result = await tool_disp.execute_tool("cancel_appointment", args)
        return json.dumps(result)

    @llm.function_tool(
        name="get_clinic_info",
        description="Retrieve official clinic hours, dentists, fixed prices, emergency policies, and location.",
    )
    async def get_clinic_info() -> str:
        """Get clinic practice info, working hours, and fixed fee list."""
        result = await tool_disp.execute_tool("get_clinic_info", {})
        return json.dumps(result)

    @llm.function_tool(
        name="take_message",
        description="Record a callback message when the clinic is closed or doctors are busy.",
    )
    async def take_message(
        caller_name: str,
        caller_phone: str,
        message: str,
        preferred_callback_time: str | None = None,
    ) -> str:
        """Record a callback message from a patient."""
        args: dict[str, Any] = {
            "caller_name": caller_name,
            "caller_phone": caller_phone,
            "message": message,
        }
        if preferred_callback_time:
            args["preferred_callback_time"] = preferred_callback_time

        result = await tool_disp.execute_tool("take_message", args)
        return json.dumps(result)

    @llm.function_tool(
        name="transfer_to_human",
        description="Transfer the call immediately to a human staff member or emergency duty surgeon.",
    )
    async def transfer_to_human(
        reason: str,
        caller_phone: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Transfer call to human operator or emergency line."""
        args: dict[str, Any] = {"reason": reason}
        if caller_phone:
            args["caller_phone"] = caller_phone
        if notes:
            args["notes"] = notes

        result = await tool_disp.execute_tool("transfer_to_human", args)
        return json.dumps(result)

    return [
        find_patient,
        check_availability,
        hold_slot,
        book_appointment,
        reschedule_appointment,
        cancel_appointment,
        get_clinic_info,
        take_message,
        transfer_to_human,
    ]
