"""Integration and unit tests for booking logic, slot holds, cancellation, and rescheduling."""

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from dentacall_core.booking import (
    AppointmentAlreadyCancelledError,
    HoldExpiredError,
    SlotUnavailableError,
    book_appointment,
    cancel_appointment,
    hold_slot,
    reschedule_appointment,
)
from dentacall_core.models import (
    Appointment,
    AppointmentStatus,
    Clinic,
    Dentist,
    Patient,
    Service,
    SlotHold,
    SlotHoldStatus,
)
from dentacall_core.settings import settings
from dentacall_core.timezone import now_utc
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest.fixture
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    """Fixture providing an isolated session with NullPool."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def seeded_entities(test_session: AsyncSession) -> dict[str, uuid.UUID]:
    clinic = Clinic(
        name="Test Dental Clinic",
        timezone="Europe/Dublin",
        phone="+35310000000",
        email="test@clinic.ie",
        emergency_phone="+35319999999",
    )
    test_session.add(clinic)
    await test_session.flush()

    dentist = Dentist(
        clinic_id=clinic.id,
        name="Dr. Test Surgeon",
        registration_number=f"IE-TEST-{uuid.uuid4().hex[:6]}",
        email="dentist@test.ie",
        phone="+353870000000",
    )
    test_session.add(dentist)

    service = Service(
        clinic_id=clinic.id,
        code=f"SRV_{uuid.uuid4().hex[:6]}",
        name="Standard Checkup",
        duration_minutes=30,
        buffer_minutes=5,
        price_eur=Decimal("65.00"),
    )
    test_session.add(service)

    patient = Patient(
        first_name="Alice",
        last_name="Tester",
        phone="+353871111111",
        email="alice@test.ie",
        date_of_birth=datetime(1990, 5, 20).date(),
    )
    test_session.add(patient)
    await test_session.commit()

    return {
        "clinic_id": clinic.id,
        "dentist_id": dentist.id,
        "service_id": service.id,
        "patient_id": patient.id,
    }


@pytest.mark.asyncio
async def test_slot_hold_lifecycle(
    test_session: AsyncSession, seeded_entities: dict[str, uuid.UUID]
) -> None:
    """Verify holding a slot, blocking second hold, and converting hold to confirmed appointment."""
    dentist_id = seeded_entities["dentist_id"]
    service_id = seeded_entities["service_id"]
    patient_id = seeded_entities["patient_id"]
    clinic_id = seeded_entities["clinic_id"]

    slot_time = now_utc() + timedelta(days=2)

    # 1. Acquire hold
    hold = await hold_slot(
        session=test_session,
        dentist_id=dentist_id,
        service_id=service_id,
        start_time_utc=slot_time,
        patient_id=patient_id,
        hold_duration_seconds=120,
    )
    assert hold.status == SlotHoldStatus.ACTIVE.value
    assert hold.held_until_utc > now_utc()
    await test_session.commit()

    # 2. Second hold attempt on same slot fails
    engine2 = create_async_engine(settings.database_url, poolclass=NullPool)
    maker2 = async_sessionmaker(bind=engine2, class_=AsyncSession, expire_on_commit=False)
    async with maker2() as s2:
        with pytest.raises(SlotUnavailableError):
            await hold_slot(
                session=s2,
                dentist_id=dentist_id,
                service_id=service_id,
                start_time_utc=slot_time,
            )
    await engine2.dispose()

    # 3. Direct booking with hold ID converts the hold to CONVERTED
    engine3 = create_async_engine(settings.database_url, poolclass=NullPool)
    maker3 = async_sessionmaker(bind=engine3, class_=AsyncSession, expire_on_commit=False)
    async with maker3() as s3:
        appt = await book_appointment(
            session=s3,
            clinic_id=clinic_id,
            patient_id=patient_id,
            dentist_id=dentist_id,
            service_id=service_id,
            start_time_utc=slot_time,
            hold_id=hold.id,
        )
        await s3.commit()

        # Check hold status is CONVERTED
        hold_in_db = await s3.get(SlotHold, hold.id)
        assert hold_in_db is not None
        assert hold_in_db.status == SlotHoldStatus.CONVERTED.value
        assert appt.status == AppointmentStatus.CONFIRMED.value
    await engine3.dispose()


@pytest.mark.asyncio
async def test_hold_expired_error(
    test_session: AsyncSession, seeded_entities: dict[str, uuid.UUID]
) -> None:
    """Verify attempting to convert an expired hold raises HoldExpiredError."""
    dentist_id = seeded_entities["dentist_id"]
    service_id = seeded_entities["service_id"]
    patient_id = seeded_entities["patient_id"]
    clinic_id = seeded_entities["clinic_id"]

    slot_time = now_utc() + timedelta(days=3)

    # Create expired hold
    expired_hold = SlotHold(
        dentist_id=dentist_id,
        service_id=service_id,
        patient_id=patient_id,
        start_time_utc=slot_time,
        end_time_utc=slot_time + timedelta(minutes=35),
        held_until_utc=now_utc() - timedelta(seconds=1),  # Already expired
        status=SlotHoldStatus.ACTIVE.value,
    )
    test_session.add(expired_hold)
    await test_session.commit()

    with pytest.raises(HoldExpiredError):
        await book_appointment(
            session=test_session,
            clinic_id=clinic_id,
            patient_id=patient_id,
            dentist_id=dentist_id,
            service_id=service_id,
            start_time_utc=slot_time,
            hold_id=expired_hold.id,
        )


@pytest.mark.asyncio
async def test_cancellation_24_hour_rule(
    test_session: AsyncSession, seeded_entities: dict[str, uuid.UUID]
) -> None:
    """Verify that cancellation >= 24h is standard and < 24h incurs late penalty flag."""
    dentist_id = seeded_entities["dentist_id"]
    service_id = seeded_entities["service_id"]
    patient_id = seeded_entities["patient_id"]
    clinic_id = seeded_entities["clinic_id"]

    now = now_utc()

    # Case A: Appointment 48 hours in future (>= 24 hours notice)
    appt_future = await book_appointment(
        session=test_session,
        clinic_id=clinic_id,
        patient_id=patient_id,
        dentist_id=dentist_id,
        service_id=service_id,
        start_time_utc=now + timedelta(hours=48),
    )
    await test_session.commit()

    cancelled_appt, is_late = await cancel_appointment(
        session=test_session,
        appointment_id=appt_future.id,
        reason="Work trip",
        cancellation_time_utc=now,
    )
    await test_session.commit()
    assert is_late is False
    assert cancelled_appt.is_late_cancellation is False
    assert cancelled_appt.status == AppointmentStatus.CANCELLED.value

    # Case B: Appointment 12 hours in future (< 24 hours notice)
    appt_soon = await book_appointment(
        session=test_session,
        clinic_id=clinic_id,
        patient_id=patient_id,
        dentist_id=dentist_id,
        service_id=service_id,
        start_time_utc=now + timedelta(hours=12),
    )
    await test_session.commit()

    cancelled_soon, is_late_soon = await cancel_appointment(
        session=test_session,
        appointment_id=appt_soon.id,
        reason="Forgot about meeting",
        cancellation_time_utc=now,
    )
    await test_session.commit()
    assert is_late_soon is True
    assert cancelled_soon.is_late_cancellation is True
    assert cancelled_soon.status == AppointmentStatus.CANCELLED.value

    # Cancelling again raises error
    with pytest.raises(AppointmentAlreadyCancelledError):
        await cancel_appointment(test_session, appt_soon.id)


@pytest.mark.asyncio
async def test_rescheduling_24_hour_rule(
    test_session: AsyncSession, seeded_entities: dict[str, uuid.UUID]
) -> None:
    """Verify that rescheduling evaluates notice on original appointment and books new slot atomically."""
    dentist_id = seeded_entities["dentist_id"]
    service_id = seeded_entities["service_id"]
    patient_id = seeded_entities["patient_id"]
    clinic_id = seeded_entities["clinic_id"]

    now = now_utc()
    orig_time = now + timedelta(hours=10)  # Inside 24h window
    new_time = now + timedelta(hours=72)

    appt = await book_appointment(
        session=test_session,
        clinic_id=clinic_id,
        patient_id=patient_id,
        dentist_id=dentist_id,
        service_id=service_id,
        start_time_utc=orig_time,
    )
    await test_session.commit()

    new_appt, is_late = await reschedule_appointment(
        session=test_session,
        appointment_id=appt.id,
        new_dentist_id=dentist_id,
        new_start_time_utc=new_time,
        reschedule_time_utc=now,
    )
    await test_session.commit()

    assert is_late is True
    assert new_appt.rescheduled_from_id == appt.id
    assert new_appt.status == AppointmentStatus.CONFIRMED.value

    # Original appointment is RESCHEDULED
    old_in_db = await test_session.get(Appointment, appt.id)
    assert old_in_db is not None
    assert old_in_db.status == AppointmentStatus.RESCHEDULED.value
    assert old_in_db.is_late_cancellation is True
