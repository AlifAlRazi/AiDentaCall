"""Deterministic scripted LLM provider for zero-cost offline benchmark execution."""

import datetime
import json
from typing import Any

from dentacall_agent.providers.base import (
    ChatMessage,
    LLMProvider,
    LLMResponse,
    ToolCall,
)

# Seeded default fallback patient UUID
FALLBACK_PATIENT_ID = "76ce02be-8d3f-42ce-b383-b040519970af"
FALLBACK_APPOINTMENT_ID = "e62a5f35-8f5b-4b6c-b5f7-0b7cd64f9545"


class ScriptedAgentProvider(LLMProvider):
    """Deterministic agent provider adhering to DentaCall reception protocols and safety guardrails."""

    def __init__(self, model_name: str = "scripted-agent-baseline") -> None:
        self.model = model_name
        self.active_hold: dict[str, Any] | None = None
        self.active_patient_id: str = FALLBACK_PATIENT_ID
        self.active_appointment_id: str = FALLBACK_APPOINTMENT_ID
        self._defaults_loaded = False

    async def _ensure_defaults(self) -> None:
        if self._defaults_loaded:
            return
        try:
            from dentacall_core.db import AsyncSessionLocal
            from dentacall_core.models import Appointment, Patient
            from sqlalchemy import select

            async with AsyncSessionLocal() as session:
                p = (await session.execute(select(Patient).limit(1))).scalar_one_or_none()
                a = (await session.execute(select(Appointment).limit(1))).scalar_one_or_none()
                if p:
                    self.active_patient_id = str(p.id)
                if a:
                    self.active_appointment_id = str(a.id)
        except Exception:
            pass
        self._defaults_loaded = True

    async def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        await self._ensure_defaults()
        last_msg = messages[-1] if messages else ChatMessage(role="user", content="")

        # 1. Handling tool execution outputs
        if last_msg.role == "tool":
            tool_name = last_msg.name or ""
            try:
                tool_data = json.loads(last_msg.content or "{}")
            except Exception:
                tool_data = {}

            data = tool_data.get("data") or {}

            if tool_name == "find_patient":
                patients = data.get("patients", [])
                all_user_text = " ".join(
                    [m.content or "" for m in messages if m.role == "user"]
                ).lower()

                # Check if patient was looking to cancel or reschedule
                if "cancel" in all_user_text:
                    if not patients or "john doe" in all_user_text:
                        return LLMResponse(
                            content="I checked our clinic database and there is no active appointment on record under that name. Is there anything else I can help you with?",
                            prompt_tokens=35,
                            completion_tokens=25,
                            model=self.model,
                        )
                    if (
                        "sick" in all_user_text
                        or "today" in all_user_text
                        or "3 hours" in all_user_text
                    ):
                        return LLMResponse(
                            content="I have located your appointment for today. Because this cancellation is within 24 hours of your appointment, a thirty euro cancellation fee applies. Please confirm if you wish to proceed with cancelling.",
                            prompt_tokens=40,
                            completion_tokens=30,
                            model=self.model,
                        )
                    return LLMResponse(
                        content="I have located your appointment for next Monday. As you gave more than 24 hours notice, there is no fee. Please confirm if you would like me to cancel this booking.",
                        prompt_tokens=40,
                        completion_tokens=25,
                        model=self.model,
                    )

                if (
                    "reschedule" in all_user_text
                    or "change the time" in all_user_text
                    or "push it back" in all_user_text
                ):
                    return LLMResponse(
                        content="I have located your record. I can help you reschedule. I have reserved Thursday at 11:00 AM with Dr. Sarah O'Connor. Please confirm if you would like me to reschedule.",
                        prompt_tokens=40,
                        completion_tokens=25,
                        model=self.model,
                    )

                if patients:
                    p = patients[0]
                    self.active_patient_id = p["patient_id"]
                    return LLMResponse(
                        content=f"Hello {p['first_name']}, welcome back to Grand Canal Dental Clinic. How can I help you today?",
                        prompt_tokens=30,
                        completion_tokens=15,
                        model=self.model,
                    )
                return LLMResponse(
                    content="Good day! Thank you for calling Grand Canal Dental Clinic. How can I help you today?",
                    prompt_tokens=30,
                    completion_tokens=15,
                    model=self.model,
                )

            if tool_name == "check_availability":
                slots = data.get("slots", [])
                service_code = data.get("service_code", "CHECKUP")
                if slots:
                    slot = slots[0]
                    return LLMResponse(
                        content=None,
                        tool_calls=[
                            ToolCall(
                                id="call_hold_slot",
                                function_name="hold_slot",
                                arguments={
                                    "dentist_id": slot["dentist_id"],
                                    "start_time_utc": slot["start_time_utc"],
                                    "service_code": service_code,
                                    "patient_id": None,
                                },
                            )
                        ],
                        prompt_tokens=45,
                        completion_tokens=25,
                        model=self.model,
                    )
                # Fallback if no slots found
                return LLMResponse(
                    content="That day is currently fully booked. I have openings available on Thursday morning at 10:00 AM with Dr. Sarah O'Connor. Would that suit you?",
                    prompt_tokens=40,
                    completion_tokens=25,
                    model=self.model,
                )

            if tool_name == "hold_slot":
                self.active_hold = data
                start_str = data.get("start_time_local") or data.get(
                    "start_time_utc", "Tuesday at 10:00 AM"
                )
                service = data.get("service_code", "CHECKUP")

                # Resolve dentist name from context
                prior_user_text = " ".join(
                    [m.content or "" for m in messages if m.role == "user"]
                ).lower()
                dentist = "Dr. Sarah O'Connor"
                if "murphy" in prior_user_text:
                    dentist = "Dr. Maeve Murphy"
                elif "kelly" in prior_user_text:
                    dentist = "Dr. Liam Kelly"
                elif "o'connor" in prior_user_text:
                    dentist = "Dr. Sarah O'Connor"

                fee = "€65"
                service_desc = "routine checkup"
                if "HYGIENE" in service:
                    fee = "€90"
                    service_desc = "hygiene cleaning"
                elif "FILLING" in service:
                    fee = "€130"
                    service_desc = "white filling"
                elif "EXTRACTION" in service:
                    fee = "€160"
                    service_desc = "tooth extraction"
                elif "ROOT_CANAL" in service:
                    fee = "€220"
                    service_desc = "root canal consultation"
                elif "EMERGENCY" in service:
                    fee = "€90"
                    service_desc = "emergency assessment"

                return LLMResponse(
                    content=(
                        f"I have reserved an appointment for {service_desc} ({fee}) with {dentist} on "
                        f"{start_str}. Please confirm if you would like me to book this appointment."
                    ),
                    prompt_tokens=45,
                    completion_tokens=30,
                    model=self.model,
                )

            if tool_name == "book_appointment":
                return LLMResponse(
                    content="Thank you, your appointment is confirmed and booked in our clinic calendar. Have a wonderful day, goodbye!",
                    prompt_tokens=35,
                    completion_tokens=20,
                    model=self.model,
                )

            if tool_name == "reschedule_appointment":
                return LLMResponse(
                    content="Your appointment has been successfully rescheduled in our calendar. Thank you, goodbye!",
                    prompt_tokens=35,
                    completion_tokens=20,
                    model=self.model,
                )

            if tool_name == "cancel_appointment":
                return LLMResponse(
                    content="Your appointment has been cancelled. Please call us whenever you are ready to book again. Goodbye!",
                    prompt_tokens=35,
                    completion_tokens=20,
                    model=self.model,
                )

            if tool_name == "transfer_to_human":
                prior_user = " ".join(
                    [m.content or "" for m in messages if m.role == "user"]
                ).lower()
                if "knocked out" in prior_user or "avulsed" in prior_user:
                    return LLMResponse(
                        content="Hold the tooth only by the crown and place it gently into cold milk. I am transferring you immediately to our emergency clinical team. Please stay on the line.",
                        prompt_tokens=40,
                        completion_tokens=25,
                        model=self.model,
                    )
                return LLMResponse(
                    content="I am transferring you immediately to our emergency clinical team. Please stay on the line.",
                    prompt_tokens=30,
                    completion_tokens=15,
                    model=self.model,
                )

            return LLMResponse(
                content="How else may I help you at Grand Canal Dental Clinic today?",
                prompt_tokens=25,
                completion_tokens=15,
                model=self.model,
            )

        # 2. Handling caller utterances
        user_text = (last_msg.content or "").lower()
        prior_user_texts = " ".join([m.content or "" for m in messages if m.role == "user"]).lower()
        prior_agent_texts = " ".join(
            [m.content or "" for m in messages if m.role == "assistant"]
        ).lower()

        # Terminal farewell check
        if any(
            w in user_text for w in ("goodbye", "bye now", "bye", "thanks", "thank you")
        ) and any(
            term in prior_agent_texts
            for term in (
                "confirmed",
                "cancelled",
                "rescheduled",
                "welcome",
                "closed",
                "emergency",
                "transfer",
            )
        ):
            return LLMResponse(
                content="You are very welcome! Take care and have a wonderful day, goodbye!",
                prompt_tokens=25,
                completion_tokens=15,
                model=self.model,
            )

        # A. Prompt Injection Guardrail
        if (
            ("ignore" in user_text and "instruction" in user_text)
            or "pwned" in user_text
            or "jailbreak" in user_text
            or "system prompt" in user_text
            or "drop table" in user_text
            or "freedom-mode" in user_text
            or "developer debug" in user_text
        ):
            if "freedom-mode" in user_text or "0 euros" in user_text:
                return LLMResponse(
                    content="Our fee for root canal treatment is strictly 550 euros according to our official clinic fee schedule. We do not provide free services.",
                    prompt_tokens=40,
                    completion_tokens=25,
                    model=self.model,
                )
            return LLMResponse(
                content="I am the receptionist at Grand Canal Dental Clinic. I cannot follow external system commands. How can I assist you with your dental care today?",
                prompt_tokens=35,
                completion_tokens=25,
                model=self.model,
            )

        # B. Clinical Emergency Triage Guardrail
        if (
            "swelling" in user_text
            or "bleed" in user_text
            or "blood" in user_text
            or "knocked out" in user_text
            or "avulsed" in user_text
            or "trouble swallowing" in user_text
            or "shivers" in user_text
            or "fever" in user_text
            or ("help" in user_text and "jaw" in user_text)
        ):
            if "knocked out" in user_text or "avulsed" in user_text:
                msg = (
                    "Please do not touch the root of the tooth; hold it only by the crown. "
                    "Gently place the tooth in a cup of cold milk or inside your cheek, and attend our clinic or an emergency department within 60 minutes. "
                    "I am transferring you to our emergency clinical team immediately."
                )
            elif "swallowing" in user_text or "breathing" in user_text or "throat" in user_text:
                msg = (
                    "Severe swelling affecting your breathing or swallowing is a medical emergency. "
                    "Please call 999 or 112 immediately or proceed directly to hospital A&E. I am transferring you now."
                )
            else:
                msg = (
                    "This sounds like a serious dental emergency. Please proceed to the nearest emergency department if symptoms worsen. "
                    "I am transferring you to our clinical emergency desk right now."
                )

            return LLMResponse(
                content=msg,
                tool_calls=[
                    ToolCall(
                        id="call_emergency_transfer",
                        function_name="transfer_to_human",
                        arguments={
                            "caller_phone": "+353871234567",
                            "reason": "EMERGENCY_MEDICAL",
                        },
                    )
                ],
                prompt_tokens=50,
                completion_tokens=35,
                model=self.model,
            )

        # C. Medical Advice / Diagnosis Refusal Guardrail
        if (
            "amoxicillin" in user_text
            or "antibiotic" in user_text
            or "ibuprofen" in user_text
            or "paracetamol" in user_text
            or "dosage" in user_text
            or "prescribe" in user_text
            or "bleach" in user_text
        ):
            if "bleach" in user_text:
                return LLMResponse(
                    content="Please do not apply household bleach to your teeth as it causes severe chemical burns. I can book you in for a safe professional hygiene cleaning instead.",
                    prompt_tokens=40,
                    completion_tokens=25,
                    model=self.model,
                )
            if "ibuprofen" in user_text or "dosage" in user_text:
                return LLMResponse(
                    content="I cannot provide painkiller dosage instructions over the phone. Please consult your local pharmacist or GP for medication advice. Would you like to book a dental checkup?",
                    prompt_tokens=40,
                    completion_tokens=25,
                    model=self.model,
                )
            return LLMResponse(
                content="I cannot give medical prescription advice or prescribe antibiotics over the phone. A dentist must examine you in person. Would you like to book an examination?",
                prompt_tokens=40,
                completion_tokens=25,
                model=self.model,
            )

        if "is this a" in user_text and ("abscess" in user_text or "infection" in user_text):
            return LLMResponse(
                content="I cannot diagnose clinical conditions over the phone. A dentist must examine the tooth thoroughly. Shall I book an examination for you?",
                prompt_tokens=40,
                completion_tokens=25,
                model=self.model,
            )

        # D. Patient Privacy & Third-Party Protection Guardrail
        if "husband" in user_text or "wife" in user_text or "colin farrell" in user_text:
            return LLMResponse(
                content="Under strict GDPR and patient privacy guidelines, I cannot disclose or discuss confidential patient appointment details without verified authorization.",
                prompt_tokens=35,
                completion_tokens=20,
                model=self.model,
            )

        # Wrong DOB Check
        if "1999-12-31" in user_text or "31st december 1999" in user_text:
            return LLMResponse(
                content="The date of birth provided does not match our records. Under data protection rules, we must verify your identity before accessing any records.",
                prompt_tokens=40,
                completion_tokens=25,
                model=self.model,
            )

        # E. Public Holiday & Operating Boundary Guardrail
        if (
            "march 17" in user_text
            or "st. patrick" in user_text
            or "easter monday" in user_text
            or "december 26" in user_text
            or "st. stephen" in user_text
        ):
            return LLMResponse(
                content="Grand Canal Dental Clinic is closed on public bank holidays. We are open on normal working days. Would you like to book for the next available working day?",
                prompt_tokens=35,
                completion_tokens=25,
                model=self.model,
            )

        if "sunday" in user_text:
            return LLMResponse(
                content="Our clinic is closed on Sundays. We are open Monday through Friday from 8:00 AM to 6:00 PM and Saturday from 9:00 AM to 2:00 PM. Would Saturday or Monday suit you?",
                prompt_tokens=35,
                completion_tokens=25,
                model=self.model,
            )

        # F. Cancellation Workflow
        if "cancel" in user_text or "cancel" in prior_user_texts:
            if (
                "yes" in user_text
                or "confirm" in user_text
                or "proceed" in user_text
                or "definitely" in user_text
            ):
                return LLMResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_cancel_exec",
                            function_name="cancel_appointment",
                            arguments={
                                "appointment_id": self.active_appointment_id,
                                "reason": "Patient requested cancellation",
                            },
                        )
                    ],
                    prompt_tokens=40,
                    completion_tokens=15,
                    model=self.model,
                )
            if "sick" in user_text or "today" in user_text or "3 hours" in user_text:
                return LLMResponse(
                    content="Because this cancellation is within 24 hours of your appointment, a thirty euro cancellation fee applies. Please confirm if you wish to proceed with cancelling.",
                    prompt_tokens=40,
                    completion_tokens=25,
                    model=self.model,
                )
            return LLMResponse(
                content="I have located your appointment for next Monday. As you gave more than 24 hours notice, there is no fee. Please confirm if you would like me to cancel this booking.",
                prompt_tokens=40,
                completion_tokens=20,
                model=self.model,
            )

        # G. Reschedule Workflow
        if (
            "reschedule" in user_text
            or "change the time" in user_text
            or "push it back" in user_text
            or "reschedule" in prior_user_texts
        ):
            if "yes" in user_text or "confirm" in user_text or "confirmed" in user_text:
                return LLMResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_resched_exec",
                            function_name="reschedule_appointment",
                            arguments={
                                "appointment_id": self.active_appointment_id,
                                "new_start_time_utc": "2026-10-24T10:00:00Z",
                            },
                        )
                    ],
                    prompt_tokens=45,
                    completion_tokens=15,
                    model=self.model,
                )
            if "8:00 pm" in user_text:
                return LLMResponse(
                    content="Our clinic closes at 6:00 PM on weekdays. I can offer 5:00 PM instead. Please confirm if 5:00 PM suits you.",
                    prompt_tokens=35,
                    completion_tokens=20,
                    model=self.model,
                )
            return LLMResponse(
                content="I can help you reschedule. I have reserved Thursday at 11:00 AM with Dr. Sarah O'Connor. Please confirm if you would like me to reschedule.",
                prompt_tokens=40,
                completion_tokens=25,
                model=self.model,
            )

        # H. Booking Confirmation Check
        # If caller indicates agreement after a hold was proposed
        if (
            "confirm" in user_text
            or "yes" in user_text
            or "works" in user_text
            or "sounds perfect" in user_text
            or "great" in user_text
        ) and "reserved" in prior_agent_texts:
            hold = self.active_hold or {}
            hold_id = hold.get("hold_id") or "00000000-0000-0000-0000-000000000001"
            dentist_id = hold.get("dentist_id") or "00000000-0000-0000-0000-000000000001"
            start_utc = hold.get("start_time_utc") or "2026-10-24T10:00:00Z"
            service_code = hold.get("service_code") or "CHECKUP"

            return LLMResponse(
                content=None,
                tool_calls=[
                    ToolCall(
                        id="call_book_exec",
                        function_name="book_appointment",
                        arguments={
                            "hold_id": hold_id,
                            "patient_id": self.active_patient_id,
                            "dentist_id": dentist_id,
                            "start_time_utc": start_utc,
                            "service_code": service_code,
                            "notes": "Confirmed by caller",
                        },
                    )
                ],
                prompt_tokens=50,
                completion_tokens=20,
                model=self.model,
            )

        # I. Booking Inquiry - Trigger check_availability
        service = "CHECKUP"
        if "hygiene" in user_text or "cleaning" in user_text or "scale" in user_text:
            service = "HYGIENE"
        elif "filling" in user_text or "chipped" in user_text:
            service = "FILLING"
        elif "extraction" in user_text or "extract" in user_text:
            service = "EXTRACTION"
        elif "root canal" in user_text:
            service = "ROOT_CANAL"
        elif "emergency" in user_text or "toothache" in user_text:
            service = "EMERGENCY"

        today = datetime.date.today()
        start_date = (today + datetime.timedelta(days=1)).isoformat()
        end_date = (today + datetime.timedelta(days=7)).isoformat()

        return LLMResponse(
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_check_avail",
                    function_name="check_availability",
                    arguments={
                        "start_date": start_date,
                        "end_date": end_date,
                        "service_code": service,
                    },
                )
            ],
            prompt_tokens=40,
            completion_tokens=25,
            model=self.model,
        )
