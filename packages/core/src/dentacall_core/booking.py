"""Booking service for appointment creation, slot holding, rescheduling, and cancellation."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from dentacall_core.models import (
    Appointment,
    AppointmentStatus,
    Service,
    SlotHold,
    SlotHoldStatus,
)
from dentacall_core.timezone import now_utc, to_utc


class BookingError(Exception):
    """Base class for booking service errors."""

    pass


class SlotUnavailableError(BookingError):
    """Raised when the requested slot overlaps with an existing appointment or hold."""

    pass


class HoldExpiredError(BookingError):
    """Raised when attempting to convert an expired or invalid slot hold."""

    pass


class AppointmentNotFoundError(BookingError):
    """Raised when an appointment ID cannot be found."""

    pass


class AppointmentAlreadyCancelledError(BookingError):
    """Raised when attempting to cancel an appointment that is already cancelled."""

    pass


async def hold_slot(
    session: AsyncSession,
    dentist_id: uuid.UUID,
    service_id: uuid.UUID,
    start_time_utc: datetime,
    patient_id: uuid.UUID | None = None,
    hold_duration_seconds: int = 120,
) -> SlotHold:
    """Acquire a temporary 2-minute hold on a slot to prevent race conditions during caller confirmation."""
    start_utc = to_utc(start_time_utc)
    now = now_utc()

    if start_utc < now:
        raise SlotUnavailableError("Cannot hold a slot in the past.")

    # 1. Load service to compute slot duration
    service_res = await session.execute(
        select(Service).where(Service.id == service_id, Service.is_active.is_(True))
    )
    service = service_res.scalar_one_or_none()
    if not service:
        raise BookingError(f"Active service {service_id} not found.")

    total_minutes = service.duration_minutes + service.buffer_minutes
    end_utc = start_utc + timedelta(minutes=total_minutes)
    held_until_utc = now + timedelta(seconds=hold_duration_seconds)

    # 2. Check overlap with existing non-cancelled appointments
    appt_stmt = select(Appointment.id).where(
        Appointment.dentist_id == dentist_id,
        Appointment.status != AppointmentStatus.CANCELLED.value,
        Appointment.start_time_utc < end_utc,
        Appointment.end_time_utc > start_utc,
    )
    overlapping_appt = (await session.execute(appt_stmt)).scalar_one_or_none()
    if overlapping_appt:
        raise SlotUnavailableError("Slot is already booked by another appointment.")

    # 3. Check overlap with active slot holds
    hold_stmt = select(SlotHold.id).where(
        SlotHold.dentist_id == dentist_id,
        SlotHold.status == SlotHoldStatus.ACTIVE.value,
        SlotHold.held_until_utc > now,
        SlotHold.start_time_utc < end_utc,
        SlotHold.end_time_utc > start_utc,
    )
    overlapping_hold = (await session.execute(hold_stmt)).scalar_one_or_none()
    if overlapping_hold:
        raise SlotUnavailableError("Slot is currently held by another caller.")

    slot_hold = SlotHold(
        dentist_id=dentist_id,
        service_id=service_id,
        patient_id=patient_id,
        start_time_utc=start_utc,
        end_time_utc=end_utc,
        held_until_utc=held_until_utc,
        status=SlotHoldStatus.ACTIVE.value,
        created_at_utc=now,
    )
    session.add(slot_hold)
    await session.flush()
    return slot_hold


async def release_hold(session: AsyncSession, hold_id: uuid.UUID) -> bool:
    """Release an active slot hold early."""
    hold_res = await session.execute(select(SlotHold).where(SlotHold.id == hold_id))
    hold = hold_res.scalar_one_or_none()
    if hold and hold.status == SlotHoldStatus.ACTIVE.value:
        hold.status = SlotHoldStatus.RELEASED.value
        await session.flush()
        return True
    return False


async def book_appointment(
    session: AsyncSession,
    clinic_id: uuid.UUID,
    patient_id: uuid.UUID,
    dentist_id: uuid.UUID,
    service_id: uuid.UUID,
    start_time_utc: datetime,
    hold_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> Appointment:
    """Confirm and book an appointment with database constraint concurrency protection."""
    start_utc = to_utc(start_time_utc)
    now = now_utc()

    if start_utc < now:
        raise SlotUnavailableError("Cannot book an appointment in the past.")

    # 1. Verify and convert hold if provided
    if hold_id:
        hold_res = await session.execute(
            select(SlotHold).where(SlotHold.id == hold_id).with_for_update()
        )
        hold = hold_res.scalar_one_or_none()
        if not hold:
            raise HoldExpiredError(f"Hold {hold_id} not found.")
        if hold.status != SlotHoldStatus.ACTIVE.value or hold.held_until_utc < now:
            raise HoldExpiredError("Slot hold has expired or was already used.")
        if hold.dentist_id != dentist_id or hold.start_time_utc != start_utc:
            raise BookingError("Hold parameters do not match requested appointment.")
        hold.status = SlotHoldStatus.CONVERTED.value

    # 2. Load service details
    service_res = await session.execute(
        select(Service).where(Service.id == service_id, Service.is_active.is_(True))
    )
    service = service_res.scalar_one_or_none()
    if not service:
        raise BookingError(f"Active service {service_id} not found.")

    end_utc = start_utc + timedelta(minutes=service.duration_minutes + service.buffer_minutes)

    appointment = Appointment(
        clinic_id=clinic_id,
        patient_id=patient_id,
        dentist_id=dentist_id,
        service_id=service_id,
        start_time_utc=start_utc,
        end_time_utc=end_utc,
        clinical_duration_minutes=service.duration_minutes,
        buffer_duration_minutes=service.buffer_minutes,
        status=AppointmentStatus.CONFIRMED.value,
        notes=notes,
        created_at_utc=now,
        updated_at_utc=now,
    )
    session.add(appointment)

    try:
        # Flushing triggers PostgreSQL GiST Exclusion Constraint immediately
        await session.flush()
    except (IntegrityError, DBAPIError) as exc:
        await session.rollback()
        raise SlotUnavailableError(
            "This slot has already been booked by another appointment."
        ) from exc

    return appointment


async def cancel_appointment(
    session: AsyncSession,
    appointment_id: uuid.UUID,
    reason: str | None = None,
    cancellation_time_utc: datetime | None = None,
) -> tuple[Appointment, bool]:
    """Cancel an appointment and enforce the 24-hour notice policy.

    Returns:
        tuple[Appointment, bool]: (cancelled_appointment, is_late_cancellation)
    """
    cancel_time = to_utc(cancellation_time_utc or now_utc())

    appt_res = await session.execute(
        select(Appointment).where(Appointment.id == appointment_id).with_for_update()
    )
    appointment = appt_res.scalar_one_or_none()
    if not appointment:
        raise AppointmentNotFoundError(f"Appointment {appointment_id} not found.")

    if appointment.status == AppointmentStatus.CANCELLED.value:
        raise AppointmentAlreadyCancelledError("Appointment is already cancelled.")

    # 24-hour rule check
    hours_notice = (appointment.start_time_utc - cancel_time).total_seconds() / 3600.0
    is_late = hours_notice < 24.0

    appointment.status = AppointmentStatus.CANCELLED.value
    appointment.is_late_cancellation = is_late
    appointment.cancellation_reason = reason
    appointment.cancelled_at_utc = cancel_time
    appointment.updated_at_utc = cancel_time

    await session.flush()
    return appointment, is_late


async def reschedule_appointment(
    session: AsyncSession,
    appointment_id: uuid.UUID,
    new_dentist_id: uuid.UUID,
    new_start_time_utc: datetime,
    reschedule_time_utc: datetime | None = None,
) -> tuple[Appointment, bool]:
    """Reschedule an existing appointment to a new slot while auditing the 24-hour policy.

    Returns:
        tuple[Appointment, bool]: (new_appointment, is_late_reschedule)
    """
    reschedule_time = to_utc(reschedule_time_utc or now_utc())
    new_start_utc = to_utc(new_start_time_utc)

    # 1. Load existing appointment
    appt_res = await session.execute(
        select(Appointment).where(Appointment.id == appointment_id).with_for_update()
    )
    old_appointment = appt_res.scalar_one_or_none()
    if not old_appointment:
        raise AppointmentNotFoundError(f"Appointment {appointment_id} not found.")

    if old_appointment.status == AppointmentStatus.CANCELLED.value:
        raise BookingError("Cannot reschedule an appointment that has been cancelled.")

    # 24-hour rule evaluation on the original appointment
    hours_notice = (old_appointment.start_time_utc - reschedule_time).total_seconds() / 3600.0
    is_late = hours_notice < 24.0

    # 2. Mark old appointment as RESCHEDULED
    old_appointment.status = AppointmentStatus.RESCHEDULED.value
    old_appointment.is_late_cancellation = is_late
    old_appointment.updated_at_utc = reschedule_time

    # 3. Create the replacement appointment atomically
    new_appointment = await book_appointment(
        session=session,
        clinic_id=old_appointment.clinic_id,
        patient_id=old_appointment.patient_id,
        dentist_id=new_dentist_id,
        service_id=old_appointment.service_id,
        start_time_utc=new_start_utc,
        notes=f"Rescheduled from appointment {old_appointment.id}",
    )
    new_appointment.rescheduled_from_id = old_appointment.id
    await session.flush()

    return new_appointment, is_late
