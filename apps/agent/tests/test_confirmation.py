"""Acceptance tests verifying confirmation before every write action and reading details back."""

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
async def test_booking_requires_confirmation_and_reads_details_back(
    test_agent: DentaCallAgent,
    mock_provider: MockProvider,
    test_session: AsyncSession,
) -> None:
    """Acceptance test: Agent reads back details (date, time, dentist, price) and asks for confirmation."""
    # Find active dentist and patient from seed
    dentist = (await test_session.execute(select(Dentist).limit(1))).scalar_one()
    patient = (await test_session.execute(select(Patient).limit(1))).scalar_one()
    target_start = now_utc() + timedelta(days=2, hours=10)

    # 1. First turn: user asks for an appointment
    # Provider holds slot and reads details back asking for confirmation
    mock_provider.enqueue(
        content="I have held a slot with Dr. Sean O'Connor on Wednesday at 10:00 for a routine dental check-up at sixty-five euro. Would you like me to confirm this booking for you?",
        tool_calls=[
            ToolCall(
                id="hold-1",
                function_name="hold_slot",
                arguments={
                    "dentist_id": str(dentist.id),
                    "service_code": "CHECKUP",
                    "start_time_utc": target_start.isoformat(),
                    "patient_id": str(patient.id),
                },
            )
        ],
    )
    # Post-tool LLM response after hold
    mock_provider.enqueue(
        content="I have Dr. Sean O'Connor on Wednesday at 10:00 AM for a routine examination at sixty-five euro. Would you like me to go ahead and book this for you?"
    )

    resp1 = await test_agent.step("I'd like to book a checkup with Dr. O'Connor on Wednesday.")

    # Verify details are read back in the spoken response
    assert "sixty-five euro" in resp1.lower() or "€65" in resp1
    assert "dr. sean o'connor" in resp1.lower() or "dr. o'connor" in resp1.lower()
    assert "would you like me to" in resp1.lower() or "confirm" in resp1.lower()

    # Slot must be held
    assert test_agent.state.active_hold_id is not None

    # 2. Second turn: Caller confirms ("Yes, please go ahead and book it")
    mock_provider.enqueue(
        content="Perfect! Your appointment with Dr. Sean O'Connor is confirmed for Wednesday at 10:00 AM.",
        tool_calls=[
            ToolCall(
                id="book-1",
                function_name="book_appointment",
                arguments={
                    "patient_id": str(patient.id),
                    "dentist_id": str(dentist.id),
                    "service_code": "CHECKUP",
                    "start_time_utc": target_start.isoformat(),
                    "hold_id": str(test_agent.state.active_hold_id),
                    "notes": "Booked via AI receptionist",
                },
            )
        ],
    )
    mock_provider.enqueue(
        content="Your appointment has been confirmed with Dr. O'Connor for Wednesday at 10:00 AM. We look forward to seeing you!"
    )

    resp2 = await test_agent.step("Yes, please confirm that booking.")

    assert "confirmed" in resp2.lower()
    # Verify appointment was committed in database
    appts = (
        (
            await test_session.execute(
                select(Appointment).where(
                    Appointment.patient_id == patient.id,
                    Appointment.dentist_id == dentist.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(appts) >= 1


@pytest.mark.asyncio
async def test_cancellation_warns_of_policy_and_confirms(
    test_agent: DentaCallAgent,
    mock_provider: MockProvider,
    test_session: AsyncSession,
) -> None:
    """Acceptance test: Cancellation warns of 24h notice policy and asks for confirmation."""
    patient = (await test_session.execute(select(Patient).limit(1))).scalar_one()
    dentist = (await test_session.execute(select(Dentist).limit(1))).scalar_one()
    service = (await test_session.execute(select(Service).limit(1))).scalar_one()

    # Create appointment 12 hours from now (< 24h)
    start_time = now_utc() + timedelta(hours=12)
    end_time = start_time + timedelta(minutes=30)
    appt = Appointment(
        clinic_id=dentist.clinic_id,
        patient_id=patient.id,
        dentist_id=dentist.id,
        service_id=service.id,
        start_time_utc=start_time,
        end_time_utc=end_time,
        clinical_duration_minutes=service.duration_minutes,
        buffer_duration_minutes=service.buffer_minutes,
        status="CONFIRMED",
    )
    test_session.add(appt)
    await test_session.commit()

    # 1. First turn: user asks to cancel
    mock_provider.enqueue(
        content="Because your appointment is within 24 hours, a thirty euro late cancellation fee will apply to your account. Would you like me to proceed with cancelling it?"
    )

    resp1 = await test_agent.step(f"I need to cancel my appointment {appt.id}.")
    assert "thirty euro" in resp1.lower() or "€30" in resp1 or "24 hours" in resp1
    assert (
        "proceed" in resp1.lower()
        or "confirm" in resp1.lower()
        or "would you like" in resp1.lower()
    )

    # 2. Second turn: caller confirms cancellation
    mock_provider.enqueue(
        content="Your appointment has been cancelled. A thirty euro late cancellation notice has been recorded.",
        tool_calls=[
            ToolCall(
                id="cancel-1",
                function_name="cancel_appointment",
                arguments={
                    "appointment_id": str(appt.id),
                    "reason": "Caller requested late cancellation",
                },
            )
        ],
    )
    mock_provider.enqueue(
        content="Your appointment is now cancelled. We hope to see you again soon."
    )

    resp2 = await test_agent.step("Yes, please cancel it anyway.")
    assert "cancelled" in resp2.lower()

    # Verify appointment updated in DB
    refreshed_appt = (
        await test_session.execute(select(Appointment).where(Appointment.id == appt.id))
    ).scalar_one()
    assert refreshed_appt.status == "CANCELLED"
    assert refreshed_appt.is_late_cancellation is True
