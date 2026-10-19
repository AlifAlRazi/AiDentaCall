"""Unit tests for the availability engine: working hours, breaks, holidays, time off, and buffers."""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from dentacall_core.availability import compute_free_slots_for_dentist_day
from dentacall_core.models import (
    Appointment,
    AppointmentStatus,
    Dentist,
    Service,
    SlotHold,
    SlotHoldStatus,
    WorkingHours,
)
from dentacall_core.timezone import DUBLIN_TZ, to_utc


@pytest.fixture
def sample_dentist() -> Dentist:
    return Dentist(
        id=uuid.uuid4(),
        clinic_id=uuid.uuid4(),
        name="Dr. Sean O'Connor",
        registration_number="IE-DEN-44821",
        email="sean@example.ie",
        phone="+353871234567",
        is_active=True,
    )


@pytest.fixture
def regular_working_hours(sample_dentist: Dentist) -> WorkingHours:
    return WorkingHours(
        id=uuid.uuid4(),
        dentist_id=sample_dentist.id,
        day_of_week=1,  # Tuesday
        start_time=time(9, 0),
        end_time=time(17, 0),
        break_start_time=time(13, 0),
        break_end_time=time(14, 0),
        is_working=True,
    )


@pytest.fixture
def checkup_service() -> Service:
    # 30 min clinical + 5 min buffer = 35 min total
    return Service(
        id=uuid.uuid4(),
        clinic_id=uuid.uuid4(),
        code="CHECKUP",
        name="Routine Examination",
        duration_minutes=30,
        buffer_minutes=5,
        price_eur=Decimal("65.00"),
        is_active=True,
    )


def test_regular_day_slot_generation(
    sample_dentist: Dentist,
    regular_working_hours: WorkingHours,
    checkup_service: Service,
) -> None:
    """Verify slots are generated within shift, excluding lunch break and respecting step."""
    test_day = date(2026, 6, 9)  # Regular Tuesday (not holiday)
    ref_now_utc = to_utc(datetime(2026, 6, 8, 8, 0, tzinfo=DUBLIN_TZ))

    slots = compute_free_slots_for_dentist_day(
        day=test_day,
        dentist=sample_dentist,
        working_hours=regular_working_hours,
        service=checkup_service,
        appointments=[],
        slot_holds=[],
        time_offs=[],
        step_minutes=15,
        reference_now_utc=ref_now_utc,
    )

    assert len(slots) > 0
    # First slot should start at shift start (09:00)
    assert slots[0].start_time_local.time() == time(9, 0)
    assert slots[0].clinical_duration_minutes == 30
    assert slots[0].buffer_minutes == 5
    assert slots[0].end_time_local.time() == time(9, 35)

    # No slot should overlap with 13:00 - 14:00 lunch break
    for slot in slots:
        start_t = slot.start_time_local.time()
        end_t = slot.end_time_local.time()
        # Cannot start inside break
        assert not (time(13, 0) <= start_t < time(14, 0))
        # Cannot end inside break if started before 13:00
        if start_t < time(13, 0):
            assert end_t <= time(13, 0), f"Slot starting at {start_t} ends at {end_t} during lunch!"

    # Last slot cannot exceed shift end (17:00).
    # Since total slot is 35m, a 16:30 slot ends at 17:05 (exceeds 17:00), so latest slot is 16:15 -> 16:50.
    last_slot = slots[-1]
    assert last_slot.end_time_local.time() <= time(17, 0)
    assert last_slot.start_time_local.time() == time(16, 15)


def test_buffer_rule_enforcement(
    sample_dentist: Dentist,
    regular_working_hours: WorkingHours,
) -> None:
    """Verify buffer time is part of the total slot reservation."""
    # Service with 45m clinical + 15m buffer = 60m total
    extraction_service = Service(
        id=uuid.uuid4(),
        clinic_id=uuid.uuid4(),
        code="EXTRACTION",
        name="Tooth Extraction",
        duration_minutes=45,
        buffer_minutes=15,
        price_eur=Decimal("140.00"),
        is_active=True,
    )

    test_day = date(2026, 6, 9)
    ref_now_utc = to_utc(datetime(2026, 6, 8, 8, 0, tzinfo=DUBLIN_TZ))

    slots = compute_free_slots_for_dentist_day(
        day=test_day,
        dentist=sample_dentist,
        working_hours=regular_working_hours,
        service=extraction_service,
        appointments=[],
        slot_holds=[],
        time_offs=[],
        step_minutes=15,
        reference_now_utc=ref_now_utc,
    )

    # A 60m slot starting at 12:15 ends at 13:15, which overlaps lunch (13:00) -> invalid
    start_times = [s.start_time_local.time() for s in slots]
    assert time(12, 15) not in start_times
    # Last morning slot must be 12:00 -> 13:00
    assert time(12, 0) in start_times
    # Afternoon starts at 14:00
    assert time(14, 0) in start_times


def test_holiday_exclusion(
    sample_dentist: Dentist,
    regular_working_hours: WorkingHours,
    checkup_service: Service,
) -> None:
    """Verify that no slots are available on statutory Irish public holidays."""
    # 2026-05-04 is May Day Bank Holiday
    may_holiday = date(2026, 5, 4)
    ref_now_utc = to_utc(datetime(2026, 5, 1, 8, 0, tzinfo=DUBLIN_TZ))

    slots = compute_free_slots_for_dentist_day(
        day=may_holiday,
        dentist=sample_dentist,
        working_hours=regular_working_hours,
        service=checkup_service,
        appointments=[],
        slot_holds=[],
        time_offs=[],
        reference_now_utc=ref_now_utc,
    )
    assert len(slots) == 0


def test_appointment_and_hold_overlap(
    sample_dentist: Dentist,
    regular_working_hours: WorkingHours,
    checkup_service: Service,
) -> None:
    """Verify that existing appointments and active holds block conflicting slots, but cancelled appts do not."""
    test_day = date(2026, 6, 9)
    ref_now_utc = to_utc(datetime(2026, 6, 8, 8, 0, tzinfo=DUBLIN_TZ))

    # Existing confirmed appointment at 10:00 (10:00 - 10:35)
    appt_start = to_utc(datetime.combine(test_day, time(10, 0), tzinfo=DUBLIN_TZ))
    appt_end = appt_start + timedelta(minutes=35)
    confirmed_appt = Appointment(
        id=uuid.uuid4(),
        clinic_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        dentist_id=sample_dentist.id,
        service_id=checkup_service.id,
        start_time_utc=appt_start,
        end_time_utc=appt_end,
        clinical_duration_minutes=30,
        buffer_duration_minutes=5,
        status=AppointmentStatus.CONFIRMED.value,
    )

    # Cancelled appointment at 11:00 (should NOT block)
    cancelled_start = to_utc(datetime.combine(test_day, time(11, 0), tzinfo=DUBLIN_TZ))
    cancelled_appt = Appointment(
        id=uuid.uuid4(),
        clinic_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        dentist_id=sample_dentist.id,
        service_id=checkup_service.id,
        start_time_utc=cancelled_start,
        end_time_utc=cancelled_start + timedelta(minutes=35),
        clinical_duration_minutes=30,
        buffer_duration_minutes=5,
        status=AppointmentStatus.CANCELLED.value,
    )

    # Active slot hold at 14:00 (14:00 - 14:35, held until future)
    hold_start = to_utc(datetime.combine(test_day, time(14, 0), tzinfo=DUBLIN_TZ))
    active_hold = SlotHold(
        id=uuid.uuid4(),
        dentist_id=sample_dentist.id,
        service_id=checkup_service.id,
        start_time_utc=hold_start,
        end_time_utc=hold_start + timedelta(minutes=35),
        held_until_utc=ref_now_utc + timedelta(minutes=2),
        status=SlotHoldStatus.ACTIVE.value,
    )

    # Expired slot hold at 15:00 (held_until in the past) -> should NOT block
    expired_start = to_utc(datetime.combine(test_day, time(15, 0), tzinfo=DUBLIN_TZ))
    expired_hold = SlotHold(
        id=uuid.uuid4(),
        dentist_id=sample_dentist.id,
        service_id=checkup_service.id,
        start_time_utc=expired_start,
        end_time_utc=expired_start + timedelta(minutes=35),
        held_until_utc=ref_now_utc - timedelta(seconds=10),
        status=SlotHoldStatus.ACTIVE.value,
    )

    slots = compute_free_slots_for_dentist_day(
        day=test_day,
        dentist=sample_dentist,
        working_hours=regular_working_hours,
        service=checkup_service,
        appointments=[confirmed_appt, cancelled_appt],
        slot_holds=[active_hold, expired_hold],
        time_offs=[],
        step_minutes=15,
        reference_now_utc=ref_now_utc,
    )

    slot_times = [s.start_time_local.time() for s in slots]

    # 10:00 is blocked by confirmed appt
    assert time(10, 0) not in slot_times
    # 09:45 is also blocked because 09:45 -> 10:20 overlaps 10:00 -> 10:35!
    assert time(9, 45) not in slot_times
    # 09:15 is free (ends at 09:50 <= 10:00)
    assert time(9, 15) in slot_times

    # 11:00 is free because appointment was cancelled
    assert time(11, 0) in slot_times

    # 14:00 is blocked by active hold
    assert time(14, 0) not in slot_times

    # 15:00 is free because hold expired
    assert time(15, 0) in slot_times
