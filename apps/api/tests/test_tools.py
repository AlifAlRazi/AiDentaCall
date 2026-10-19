"""End-to-end integration tests for all 9 voice receptionist tool endpoints."""

import uuid
from datetime import date, timedelta

import pytest
from dentacall_core.timezone import now_utc
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from data.seed import seed_database


@pytest.fixture(autouse=True)
async def seed_data(test_session: AsyncSession) -> None:
    """Seed clinic database with realistic data before running tool tests."""
    await seed_database(test_session)


@pytest.mark.asyncio
async def test_tool_get_clinic_info(client: AsyncClient) -> None:
    """Tool 7: get_clinic_info returns operating hours, 3 dentists, and 6 services."""
    res = await client.get("/tools/get_clinic_info")
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True

    data = body["data"]
    assert data["clinic_name"] == "Grand Canal Dental Clinic"
    assert data["phone"] == "+35312345678"
    assert len(data["dentists"]) == 3
    assert len(data["services"]) == 6
    assert "24 hours" in data["cancellation_policy"]


@pytest.mark.asyncio
async def test_tool_find_patient_by_phone_and_name(client: AsyncClient) -> None:
    """Tool 1: find_patient finds seeded patient by normalized phone and by name."""
    # Lookup by phone (with spacing in input)
    res_phone = await client.post("/tools/find_patient", json={"phone": "087 123 4001"})
    assert res_phone.status_code == 200
    body = res_phone.json()
    assert body["success"] is True
    assert body["data"]["total_found"] == 1
    patient = body["data"]["patients"][0]
    assert patient["first_name"] == "Conor"
    assert patient["last_name"] == "Walsh"

    # Lookup by last name
    res_name = await client.post("/tools/find_patient", json={"last_name": "Byrne"})
    assert res_name.status_code == 200
    body_name = res_name.json()
    assert body_name["data"]["total_found"] >= 1
    assert any(p["first_name"] == "Siobhan" for p in body_name["data"]["patients"])


@pytest.mark.asyncio
async def test_tool_check_availability_and_hold_slot(client: AsyncClient) -> None:
    """Tools 2 & 3: check_availability returns free slots, and hold_slot locks a slot for 2 minutes."""
    next_week = date.today() + timedelta(days=7)
    window_end = next_week + timedelta(days=5)

    # Check availability for CHECKUP
    res_avail = await client.post(
        "/tools/check_availability",
        json={
            "start_date": next_week.isoformat(),
            "end_date": window_end.isoformat(),
            "service_code": "CHECKUP",
        },
    )
    assert res_avail.status_code == 200
    body_avail = res_avail.json()
    assert body_avail["success"] is True
    slots = body_avail["data"]["slots"]
    assert len(slots) > 0

    first_slot = slots[0]
    dentist_id = first_slot["dentist_id"]
    slot_utc = first_slot["start_time_utc"]

    # Hold this slot
    res_hold = await client.post(
        "/tools/hold_slot",
        json={
            "dentist_id": dentist_id,
            "service_code": "CHECKUP",
            "start_time_utc": slot_utc,
        },
    )
    assert res_hold.status_code == 200
    body_hold = res_hold.json()
    assert body_hold["success"] is True
    assert body_hold["data"]["hold_duration_seconds"] == 120
    assert body_hold["data"]["hold_id"] is not None

    # Second hold attempt on same slot fails
    res_hold_2 = await client.post(
        "/tools/hold_slot",
        json={
            "dentist_id": dentist_id,
            "service_code": "CHECKUP",
            "start_time_utc": slot_utc,
        },
    )
    assert res_hold_2.status_code == 200
    body_hold_2 = res_hold_2.json()
    assert body_hold_2["success"] is False
    assert body_hold_2["error_code"] == "SLOT_UNAVAILABLE"


@pytest.mark.asyncio
async def test_tool_book_reschedule_cancel_workflow(client: AsyncClient) -> None:
    """Tools 4, 5 & 6: Full booking, rescheduling, and cancellation workflow."""
    # Find patient
    p_res = await client.post("/tools/find_patient", json={"last_name": "Walsh"})
    patient_id = p_res.json()["data"]["patients"][0]["patient_id"]

    # Get clinic info to find a dentist
    c_res = await client.get("/tools/get_clinic_info")
    dentist_1 = c_res.json()["data"]["dentists"][0]["dentist_id"]
    dentist_2 = c_res.json()["data"]["dentists"][1]["dentist_id"]

    booking_time = now_utc() + timedelta(days=10, hours=10)

    # 4. Book appointment
    book_res = await client.post(
        "/tools/book_appointment",
        json={
            "patient_id": patient_id,
            "dentist_id": dentist_1,
            "service_code": "CHECKUP",
            "start_time_utc": booking_time.isoformat(),
            "notes": "Routine examination",
        },
        headers={"Idempotency-Key": f"workflow-book-{uuid.uuid4()}"},
    )
    assert book_res.status_code == 200
    book_body = book_res.json()
    assert book_body["success"] is True
    appt_id = book_body["data"]["appointment_id"]

    # 5. Reschedule appointment
    new_time = now_utc() + timedelta(days=12, hours=14)
    resched_res = await client.post(
        "/tools/reschedule_appointment",
        json={
            "appointment_id": appt_id,
            "new_dentist_id": dentist_2,
            "new_start_time_utc": new_time.isoformat(),
        },
        headers={"Idempotency-Key": f"workflow-resched-{uuid.uuid4()}"},
    )
    assert resched_res.status_code == 200
    resched_body = resched_res.json()
    assert resched_body["success"] is True
    new_appt_id = resched_body["data"]["new_appointment_id"]
    assert new_appt_id != appt_id

    # 6. Cancel appointment
    cancel_res = await client.post(
        "/tools/cancel_appointment",
        json={
            "appointment_id": new_appt_id,
            "reason": "Schedule clash",
        },
        headers={"Idempotency-Key": f"workflow-cancel-{uuid.uuid4()}"},
    )
    assert cancel_res.status_code == 200
    cancel_body = cancel_res.json()
    assert cancel_body["success"] is True
    assert cancel_body["data"]["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_tool_take_message(client: AsyncClient) -> None:
    """Tool 8: take_message records callback request and returns formatted promise."""
    res = await client.post(
        "/tools/take_message",
        json={
            "caller_name": "Darren Clarke",
            "caller_phone": "087 999 8877",
            "message": "Calling to check pricing on dentures.",
            "urgency": "NORMAL",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["data"]["status"] == "LOGGED"
    assert "reception team" in body["data"]["callback_promise"]


@pytest.mark.asyncio
async def test_tool_transfer_to_human(client: AsyncClient) -> None:
    """Tool 9: transfer_to_human routes to emergency line on medical emergency."""
    # Emergency transfer
    res_emerg = await client.post(
        "/tools/transfer_to_human",
        json={
            "caller_phone": "087 111 9999",
            "reason": "EMERGENCY_MEDICAL: Facial swelling and airway pain",
        },
    )
    assert res_emerg.status_code == 200
    body_emerg = res_emerg.json()
    assert body_emerg["success"] is True
    assert body_emerg["data"]["target_phone"] == "+35312349999"
    assert "emergency duty dentist" in body_emerg["data"]["spoken_notice_for_caller"]

    # General transfer
    res_gen = await client.post(
        "/tools/transfer_to_human",
        json={
            "caller_phone": "087 111 9999",
            "reason": "CALLER_REQUEST: Wants to speak to human receptionist",
        },
    )
    assert res_gen.status_code == 200
    body_gen = res_gen.json()
    assert body_gen["success"] is True
    assert body_gen["data"]["target_phone"] == "+35312345678"
    assert "clinic reception team" in body_gen["data"]["spoken_notice_for_caller"]
