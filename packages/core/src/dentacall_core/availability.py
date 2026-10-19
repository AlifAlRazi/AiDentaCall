"""Availability engine for computing bookable appointment slots."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dentacall_core.holidays import is_irish_public_holiday
from dentacall_core.models import (
    Appointment,
    AppointmentStatus,
    Dentist,
    Service,
    SlotHold,
    SlotHoldStatus,
    TimeOff,
    WorkingHours,
)
from dentacall_core.timezone import DUBLIN_TZ, now_utc, to_utc


@dataclass(frozen=True)
class TimeSlot:
    """Represents a free, bookable appointment slot."""

    dentist_id: uuid.UUID
    dentist_name: str
    service_id: uuid.UUID
    service_code: str
    start_time_utc: datetime
    end_time_utc: datetime
    start_time_local: datetime
    end_time_local: datetime
    clinical_duration_minutes: int
    buffer_minutes: int


def _intervals_overlap(start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> bool:
    """Return True if two half-open intervals [start1, end1) and [start2, end2) overlap."""
    return max(start1, start2) < min(end1, end2)


def compute_free_slots_for_dentist_day(
    day: date,
    dentist: Dentist,
    working_hours: WorkingHours | None,
    service: Service,
    appointments: list[Appointment],
    slot_holds: list[SlotHold],
    time_offs: list[TimeOff],
    step_minutes: int = 15,
    reference_now_utc: datetime | None = None,
) -> list[TimeSlot]:
    """Calculate all available slots for one dentist on a specific calendar date."""
    now = reference_now_utc or now_utc()

    # 1. Clinic is closed on Irish statutory public holidays
    if is_irish_public_holiday(day):
        return []

    # 2. Check if dentist has working hours for this weekday
    if not working_hours or not working_hours.is_working:
        return []

    shift_start_local = datetime.combine(day, working_hours.start_time, tzinfo=DUBLIN_TZ)
    shift_end_local = datetime.combine(day, working_hours.end_time, tzinfo=DUBLIN_TZ)

    break_start_local = (
        datetime.combine(day, working_hours.break_start_time, tzinfo=DUBLIN_TZ)
        if working_hours.break_start_time
        else None
    )
    break_end_local = (
        datetime.combine(day, working_hours.break_end_time, tzinfo=DUBLIN_TZ)
        if working_hours.break_end_time
        else None
    )

    total_slot_minutes = service.duration_minutes + service.buffer_minutes
    slot_duration = timedelta(minutes=total_slot_minutes)
    step = timedelta(minutes=step_minutes)

    candidate_slots: list[TimeSlot] = []
    current_time_local = shift_start_local

    while current_time_local + slot_duration <= shift_end_local:
        candidate_end_local = current_time_local + slot_duration
        candidate_start_utc = to_utc(current_time_local)
        candidate_end_utc = to_utc(candidate_end_local)

        # Slot cannot be in the past
        if candidate_start_utc < now:
            current_time_local += step
            continue

        # Check break overlap
        is_break_conflict = bool(
            break_start_local
            and break_end_local
            and _intervals_overlap(
                current_time_local,
                candidate_end_local,
                break_start_local,
                break_end_local,
            )
        )

        if is_break_conflict:
            current_time_local += step
            continue

        # Check TimeOff overlap
        is_time_off_conflict = any(
            _intervals_overlap(
                candidate_start_utc,
                candidate_end_utc,
                to_utc(to_off.start_time_utc),
                to_utc(to_off.end_time_utc),
            )
            for to_off in time_offs
        )
        if is_time_off_conflict:
            current_time_local += step
            continue

        # Check Appointment overlap (excluding cancelled)
        is_appointment_conflict = any(
            appt.status != AppointmentStatus.CANCELLED.value
            and _intervals_overlap(
                candidate_start_utc,
                candidate_end_utc,
                to_utc(appt.start_time_utc),
                to_utc(appt.end_time_utc),
            )
            for appt in appointments
        )
        if is_appointment_conflict:
            current_time_local += step
            continue

        # Check active SlotHold overlap
        is_hold_conflict = any(
            hold.status == SlotHoldStatus.ACTIVE.value
            and to_utc(hold.held_until_utc) > now
            and _intervals_overlap(
                candidate_start_utc,
                candidate_end_utc,
                to_utc(hold.start_time_utc),
                to_utc(hold.end_time_utc),
            )
            for hold in slot_holds
        )
        if is_hold_conflict:
            current_time_local += step
            continue

        # Slot is valid and free
        candidate_slots.append(
            TimeSlot(
                dentist_id=dentist.id,
                dentist_name=dentist.name,
                service_id=service.id,
                service_code=service.code,
                start_time_utc=candidate_start_utc,
                end_time_utc=candidate_end_utc,
                start_time_local=current_time_local,
                end_time_local=candidate_end_local,
                clinical_duration_minutes=service.duration_minutes,
                buffer_minutes=service.buffer_minutes,
            )
        )

        current_time_local += step

    return candidate_slots


async def get_available_slots(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    service_id: uuid.UUID,
    dentist_id: uuid.UUID | None = None,
    step_minutes: int = 15,
) -> list[TimeSlot]:
    """Retrieve all available appointment slots from the database within a date range."""
    # 1. Load service
    service_stmt = select(Service).where(Service.id == service_id, Service.is_active.is_(True))
    service_res = await session.execute(service_stmt)
    service = service_res.scalar_one_or_none()
    if not service:
        return []

    # 2. Load dentists
    dentist_stmt = select(Dentist).where(Dentist.is_active.is_(True))
    if dentist_id:
        dentist_stmt = dentist_stmt.where(Dentist.id == dentist_id)
    dentist_stmt = dentist_stmt.options(selectinload(Dentist.working_hours))
    dentists_res = await session.execute(dentist_stmt)
    dentists = list(dentists_res.scalars().all())
    if not dentists:
        return []

    # 3. Query existing non-cancelled appointments in the date range
    range_start_utc = to_utc(datetime.combine(start_date, time.min, tzinfo=DUBLIN_TZ))
    range_end_utc = to_utc(datetime.combine(end_date, time.max, tzinfo=DUBLIN_TZ))

    appts_stmt = select(Appointment).where(
        Appointment.status != AppointmentStatus.CANCELLED.value,
        Appointment.start_time_utc < range_end_utc,
        Appointment.end_time_utc > range_start_utc,
    )
    if dentist_id:
        appts_stmt = appts_stmt.where(Appointment.dentist_id == dentist_id)
    appts_res = await session.execute(appts_stmt)
    appointments = list(appts_res.scalars().all())

    # 4. Query active slot holds
    now = now_utc()
    holds_stmt = select(SlotHold).where(
        SlotHold.status == SlotHoldStatus.ACTIVE.value,
        SlotHold.held_until_utc > now,
        SlotHold.start_time_utc < range_end_utc,
        SlotHold.end_time_utc > range_start_utc,
    )
    if dentist_id:
        holds_stmt = holds_stmt.where(SlotHold.dentist_id == dentist_id)
    holds_res = await session.execute(holds_stmt)
    slot_holds = list(holds_res.scalars().all())

    # 5. Query time offs
    timeoff_stmt = select(TimeOff).where(
        TimeOff.start_time_utc < range_end_utc,
        TimeOff.end_time_utc > range_start_utc,
    )
    timeoffs_res = await session.execute(timeoff_stmt)
    all_timeoffs = list(timeoffs_res.scalars().all())

    available_slots: list[TimeSlot] = []

    # Iterate day by day
    current_day = start_date
    while current_day <= end_date:
        for dentist in dentists:
            weekday = current_day.weekday()
            wh = next((w for w in dentist.working_hours if w.day_of_week == weekday), None)
            dentist_timeoffs = [
                to for to in all_timeoffs if to.dentist_id is None or to.dentist_id == dentist.id
            ]
            dentist_appts = [a for a in appointments if a.dentist_id == dentist.id]
            dentist_holds = [h for h in slot_holds if h.dentist_id == dentist.id]

            day_slots = compute_free_slots_for_dentist_day(
                day=current_day,
                dentist=dentist,
                working_hours=wh,
                service=service,
                appointments=dentist_appts,
                slot_holds=dentist_holds,
                time_offs=dentist_timeoffs,
                step_minutes=step_minutes,
                reference_now_utc=now,
            )
            available_slots.extend(day_slots)

        current_day += timedelta(days=1)

    available_slots.sort(key=lambda s: (s.start_time_utc, s.dentist_name))
    return available_slots
