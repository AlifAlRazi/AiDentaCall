"""Acceptance test: sending the same idempotency key twice creates exactly one booking."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from dentacall_core.models import Appointment, Clinic, Dentist, Patient, Service
from dentacall_core.timezone import now_utc
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
async def setup_entities(test_session: AsyncSession) -> dict[str, Any]:
    clinic = Clinic(
        name="Idempotency Test Clinic",
        timezone="Europe/Dublin",
        phone="+35310008888",
        email="idemp@test.ie",
        emergency_phone="+35319998888",
    )
    test_session.add(clinic)
    await test_session.flush()

    dentist = Dentist(
        clinic_id=clinic.id,
        name="Dr. Idempotent",
        registration_number=f"IE-IDEM-{uuid.uuid4().hex[:6]}",
        email="idemp.dr@test.ie",
        phone="+353878888888",
    )
    test_session.add(dentist)

    service = Service(
        clinic_id=clinic.id,
        code=f"IDM_{uuid.uuid4().hex[:6]}",
        name="Idempotency Checkup",
        duration_minutes=30,
        buffer_minutes=5,
        price_eur=Decimal("65.00"),
    )
    test_session.add(service)

    patient = Patient(
        first_name="Bob",
        last_name="Idempotent",
        phone="+353872222222",
        email="bob.idemp@test.ie",
        date_of_birth=datetime(1988, 3, 14).date(),
    )
    test_session.add(patient)
    await test_session.commit()

    return {
        "clinic_id": clinic.id,
        "dentist_id": dentist.id,
        "service_id": service.id,
        "service_code": service.code,
        "patient_id": patient.id,
    }


@pytest.mark.asyncio
async def test_same_idempotency_key_twice_creates_one_booking(
    client: AsyncClient,
    test_session: AsyncSession,
    setup_entities: dict[str, Any],
) -> None:
    """Acceptance test: Submitting the identical Idempotency-Key twice results in a single booking."""
    idempotency_key = f"key-{uuid.uuid4()}"
    start_time = now_utc() + timedelta(days=7, hours=11)

    payload = {
        "patient_id": str(setup_entities["patient_id"]),
        "dentist_id": str(setup_entities["dentist_id"]),
        "service_code": setup_entities["service_code"],
        "start_time_utc": start_time.isoformat(),
        "notes": "First booking request with idempotency key",
    }

    headers = {"Idempotency-Key": idempotency_key}

    # 1. First request
    res1 = await client.post("/tools/book_appointment", json=payload, headers=headers)
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["success"] is True
    appointment_id_1 = body1["data"]["appointment_id"]

    # 2. Second request with the exact same idempotency key
    res2 = await client.post("/tools/book_appointment", json=payload, headers=headers)
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["success"] is True
    appointment_id_2 = body2["data"]["appointment_id"]

    # 3. Both responses return identical appointment ID
    assert appointment_id_1 == appointment_id_2

    # 4. Directly query database: verify exactly ONE appointment was created
    appts = (
        (
            await test_session.execute(
                select(Appointment).where(
                    Appointment.dentist_id == setup_entities["dentist_id"],
                    Appointment.start_time_utc == start_time,
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(appts) == 1, f"Expected 1 appointment in DB, found {len(appts)}"
    assert str(appts[0].id) == appointment_id_1
