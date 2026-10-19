"""Concurrency test: 20 parallel booking attempts on one slot results in exactly one booking."""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from dentacall_core.booking import SlotUnavailableError, book_appointment
from dentacall_core.models import Appointment, Clinic, Dentist, Patient, Service
from dentacall_core.settings import settings
from dentacall_core.timezone import now_utc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest.mark.asyncio
async def test_twenty_parallel_bookings_on_same_slot() -> None:
    """Acceptance test: 20 simultaneous parallel booking attempts on the exact same dentist slot.

    PostgreSQL GiST overlap exclusion constraint and atomic transactions guarantee that
    EXACTLY ONE booking succeeds and 19 fail with SlotUnavailableError.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Setup isolated clinic, dentist, service, and 20 distinct patients
    async with session_factory() as session:
        clinic = Clinic(
            name="Concurrency Test Clinic",
            timezone="Europe/Dublin",
            phone="+35310009999",
            email="conc@test.ie",
            emergency_phone="+35319999999",
        )
        session.add(clinic)
        await session.flush()

        dentist = Dentist(
            clinic_id=clinic.id,
            name="Dr. Parallel Target",
            registration_number=f"IE-CONC-{uuid.uuid4().hex[:6]}",
            email="parallel@test.ie",
            phone="+353879998888",
        )
        session.add(dentist)

        service = Service(
            clinic_id=clinic.id,
            code=f"CONC_{uuid.uuid4().hex[:6]}",
            name="Emergency Relief",
            duration_minutes=30,
            buffer_minutes=5,
            price_eur=Decimal("80.00"),
        )
        session.add(service)

        patients = []
        for i in range(20):
            p = Patient(
                first_name=f"Patient{i}",
                last_name="Concurrent",
                phone=f"+35387{i:07d}",
                email=f"patient{i}@conc.ie",
                date_of_birth=datetime(1995, 1, 1).date(),
            )
            session.add(p)
            patients.append(p)

        await session.commit()

        clinic_id = clinic.id
        dentist_id = dentist.id
        service_id = service.id
        patient_ids = [p.id for p in patients]

    # Target the exact same appointment start time for all 20 attempts
    target_start_time = now_utc() + timedelta(days=5, hours=10)

    # 2. Worker function simulating an incoming caller booking attempt
    async def attempt_booking(worker_idx: int, pat_id: uuid.UUID) -> Appointment:
        # Each worker runs its own isolated session on the NullPool engine
        async with session_factory() as worker_session:
            appt = await book_appointment(
                session=worker_session,
                clinic_id=clinic_id,
                patient_id=pat_id,
                dentist_id=dentist_id,
                service_id=service_id,
                start_time_utc=target_start_time,
                notes=f"Concurrent caller attempt #{worker_idx}",
            )
            await worker_session.commit()
            return appt

    # 3. Fire all 20 booking attempts concurrently
    tasks = [attempt_booking(i, patient_ids[i]) for i in range(20)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 4. Verify outcomes
    successes: list[Appointment] = []
    failures: list[Exception] = []

    for res in results:
        if isinstance(res, Appointment):
            successes.append(res)
        elif isinstance(res, Exception):
            failures.append(res)
        else:
            pytest.fail(f"Unexpected result type: {type(res)}")

    # Assert exactly 1 booking succeeded
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 19, f"Expected exactly 19 failures, got {len(failures)}"

    # Assert all 19 failures are SlotUnavailableError
    for failure in failures:
        assert isinstance(failure, SlotUnavailableError), (
            f"Expected SlotUnavailableError, got {type(failure)}: {failure}"
        )

    # 5. Verify database state directly: exactly 1 appointment recorded for this dentist and slot
    async with session_factory() as verify_session:
        appts_in_db = (
            (
                await verify_session.execute(
                    select(Appointment).where(
                        Appointment.dentist_id == dentist_id,
                        Appointment.start_time_utc == target_start_time,
                    )
                )
            )
            .scalars()
            .all()
        )

        assert len(appts_in_db) == 1
        assert appts_in_db[0].id == successes[0].id

    await engine.dispose()
