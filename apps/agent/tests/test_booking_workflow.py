"""End-to-end multi-turn conversation workflows for booking, rescheduling, and messaging."""

from datetime import timedelta

import pytest
from dentacall_agent.agent import DentaCallAgent
from dentacall_agent.providers.base import ToolCall
from dentacall_agent.providers.mock_provider import MockProvider
from dentacall_core.models import Appointment, Dentist, Patient, Service
from dentacall_core.timezone import now_utc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_full_booking_workflow_multi_turn(
    test_agent: DentaCallAgent,
    mock_provider: MockProvider,
    test_session: AsyncSession,
) -> None:
    """Full end-to-end conversation: patient lookup -> check availability -> hold -> confirm -> book."""
    dentist = (await test_session.execute(select(Dentist).limit(1))).scalar_one()
    patient = (await test_session.execute(select(Patient).limit(1))).scalar_one()
    slot_time = now_utc() + timedelta(days=3, hours=9)

    # 1. Start call
    greeting = await test_agent.start_call()
    assert "Grand Canal Dental Clinic" in greeting

    # 2. Turn 1: Caller introduces self and wants a checkup
    mock_provider.enqueue(
        content="Let me look up your patient record and check our available checkup openings.",
        tool_calls=[
            ToolCall(
                id="lookup-1",
                function_name="find_patient",
                arguments={"phone": patient.phone},
            ),
            ToolCall(
                id="avail-1",
                function_name="check_availability",
                arguments={
                    "service_code": "CHECKUP",
                    "start_date": (slot_time).strftime("%Y-%m-%d"),
                    "end_date": (slot_time + timedelta(days=2)).strftime("%Y-%m-%d"),
                },
            ),
        ],
    )
    mock_provider.enqueue(
        content=f"Hello {patient.first_name}! I found open checkup slots on {slot_time.strftime('%A')}. Would 09:00 AM with Dr. O'Connor suit you?"
    )

    t1_resp = await test_agent.step(
        f"Hi, this is {patient.first_name} {patient.last_name}, my phone is {patient.phone}. I'd like a checkup."
    )
    assert patient.first_name in t1_resp or "suit you" in t1_resp or "checkup" in t1_resp.lower()
    assert test_agent.state.patient_id == patient.id

    # 3. Turn 2: Caller picks the slot -> agent holds and reads back confirmation
    mock_provider.enqueue(
        content="I have held that 09:00 AM slot for two minutes. That is Dr. O'Connor on Wednesday at 09:00 for a routine dental checkup at sixty-five euro. Shall I finalize this booking?",
        tool_calls=[
            ToolCall(
                id="hold-1",
                function_name="hold_slot",
                arguments={
                    "dentist_id": str(dentist.id),
                    "service_code": "CHECKUP",
                    "start_time_utc": slot_time.isoformat(),
                    "patient_id": str(patient.id),
                },
            )
        ],
    )
    mock_provider.enqueue(
        content="I have held the 09:00 AM slot for you. That is sixty-five euro with Dr. O'Connor. Can I confirm this booking?"
    )

    t2_resp = await test_agent.step("Yes, 09:00 AM sounds great.")
    assert (
        "held" in t2_resp.lower()
        or "sixty-five euro" in t2_resp.lower()
        or "confirm" in t2_resp.lower()
    )
    assert test_agent.state.active_hold_id is not None

    # 4. Turn 3: Caller confirms -> agent finalizes booking
    mock_provider.enqueue(
        content="Booking your appointment now.",
        tool_calls=[
            ToolCall(
                id="book-1",
                function_name="book_appointment",
                arguments={
                    "patient_id": str(patient.id),
                    "dentist_id": str(dentist.id),
                    "service_code": "CHECKUP",
                    "start_time_utc": slot_time.isoformat(),
                    "hold_id": str(test_agent.state.active_hold_id),
                    "notes": "Full workflow test booking",
                },
            )
        ],
    )
    mock_provider.enqueue(
        content="Your appointment has been confirmed for 09:00 AM with Dr. O'Connor. We will see you then!"
    )

    t3_resp = await test_agent.step("Yes, please confirm it.")
    assert "confirmed" in t3_resp.lower()

    # Verify appointment in database
    created_appt = (
        await test_session.execute(
            select(Appointment).where(
                Appointment.patient_id == patient.id,
                Appointment.start_time_utc == slot_time,
            )
        )
    ).scalar_one_or_none()
    assert created_appt is not None
    assert created_appt.status == "CONFIRMED"


@pytest.mark.asyncio
async def test_take_message_workflow(
    test_agent: DentaCallAgent,
    mock_provider: MockProvider,
) -> None:
    """Agent takes a caller callback message when appropriate."""
    mock_provider.enqueue(
        content="I have recorded your callback request for our reception desk.",
        tool_calls=[
            ToolCall(
                id="msg-1",
                function_name="take_message",
                arguments={
                    "caller_name": "Mary Higgins",
                    "caller_phone": "+353875554433",
                    "message": "Please call back regarding weekend teeth whitening inquiries.",
                    "urgency": "NORMAL",
                },
            )
        ],
    )
    mock_provider.enqueue(
        content="Thank you, Mary. I have logged your message and our reception team will call you back as soon as possible."
    )

    resp = await test_agent.step("Could someone call me back about teeth whitening options?")
    assert "logged" in resp.lower() or "message" in resp.lower() or "call you back" in resp.lower()


@pytest.mark.asyncio
async def test_reschedule_workflow(
    test_agent: DentaCallAgent,
    mock_provider: MockProvider,
    test_session: AsyncSession,
) -> None:
    """Agent verifies identity, checks availability, and reschedules an existing appointment."""
    dentist = (await test_session.execute(select(Dentist).limit(1))).scalar_one()
    patient = (await test_session.execute(select(Patient).limit(1))).scalar_one()
    service = (await test_session.execute(select(Service).limit(1))).scalar_one()

    # Create original appointment 3 days out (> 24 hours notice)
    orig_start = now_utc() + timedelta(days=3, hours=10)
    orig_end = orig_start + timedelta(minutes=30)
    orig_appt = Appointment(
        clinic_id=dentist.clinic_id,
        patient_id=patient.id,
        dentist_id=dentist.id,
        service_id=service.id,
        start_time_utc=orig_start,
        end_time_utc=orig_end,
        clinical_duration_minutes=service.duration_minutes,
        buffer_duration_minutes=service.buffer_minutes,
        status="CONFIRMED",
    )
    test_session.add(orig_appt)
    await test_session.commit()

    new_start = now_utc() + timedelta(days=4, hours=14)

    # Agent verifies, checks availability, and calls reschedule_appointment
    mock_provider.enqueue(
        content="I am moving your booking to Thursday at 14:00 PM with Dr. O'Connor.",
        tool_calls=[
            ToolCall(
                id="reschedule-1",
                function_name="reschedule_appointment",
                arguments={
                    "appointment_id": str(orig_appt.id),
                    "new_dentist_id": str(dentist.id),
                    "new_start_time_utc": new_start.isoformat(),
                },
            )
        ],
    )
    mock_provider.enqueue(
        content="Your appointment has been successfully rescheduled to Thursday at 14:00 with Dr. O'Connor. No fees applied as you provided over 24 hours notice."
    )

    resp = await test_agent.step(
        f"Hi, I need to reschedule appointment {orig_appt.id} to Thursday afternoon."
    )
    assert "rescheduled" in resp.lower() or "thursday" in resp.lower()

    # Verify original appointment marked as RESCHEDULED in DB
    refreshed_orig = (
        await test_session.execute(select(Appointment).where(Appointment.id == orig_appt.id))
    ).scalar_one()
    assert refreshed_orig.status == "RESCHEDULED"
