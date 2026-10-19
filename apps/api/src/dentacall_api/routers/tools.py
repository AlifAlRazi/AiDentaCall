"""FastAPI router implementing all 9 voice receptionist tool endpoints."""

import uuid
from decimal import Decimal

from dentacall_api.auth import verify_api_key
from dentacall_api.middleware.idempotency import idempotency_manager
from dentacall_api.schemas.tools import (
    BookAppointmentData,
    BookAppointmentRequest,
    CancelAppointmentData,
    CancelAppointmentRequest,
    CheckAvailabilityData,
    CheckAvailabilityRequest,
    ClinicInfoData,
    DentistInfo,
    FindPatientData,
    FindPatientRequest,
    HoldSlotData,
    HoldSlotRequest,
    PatientSummary,
    RescheduleAppointmentData,
    RescheduleAppointmentRequest,
    ServiceInfo,
    SlotSummary,
    TakeMessageData,
    TakeMessageRequest,
    ToolResult,
    TransferToHumanData,
    TransferToHumanRequest,
)
from dentacall_core.availability import get_available_slots
from dentacall_core.booking import (
    AppointmentAlreadyCancelledError,
    AppointmentNotFoundError,
    HoldExpiredError,
    SlotUnavailableError,
    book_appointment,
    cancel_appointment,
    hold_slot,
    reschedule_appointment,
)
from dentacall_core.db import get_async_session
from dentacall_core.models import (
    CallLog,
    Clinic,
    Dentist,
    Patient,
    Service,
)
from dentacall_core.settings import settings
from dentacall_core.timezone import format_dublin, to_dublin
from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(
    prefix="/tools", tags=["Receptionist Tools"], dependencies=[Depends(verify_api_key)]
)


# 1. find_patient
@router.post("/find_patient", response_model=ToolResult[FindPatientData])
async def find_patient(
    payload: FindPatientRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[FindPatientData]:
    """Look up patient records by normalized telephone number or name and birth date."""
    query = select(Patient)

    if payload.phone:
        query = query.where(Patient.phone == payload.phone)
    elif payload.last_name:
        query = query.where(Patient.last_name.ilike(payload.last_name))
        if payload.first_name:
            query = query.where(Patient.first_name.ilike(payload.first_name))
        if payload.date_of_birth:
            query = query.where(Patient.date_of_birth == payload.date_of_birth)
    else:
        return ToolResult(
            success=False,
            error_code="MISSING_SEARCH_PARAMS",
            error_message="Either 'phone' or 'last_name' must be provided to search for a patient.",
            hint="Ask the caller for their telephone number or full name and date of birth.",
        )

    results = (await session.execute(query)).scalars().all()

    summaries = [
        PatientSummary(
            patient_id=p.id,
            first_name=p.first_name,
            last_name=p.last_name,
            phone=p.phone,
            email=p.email,
            date_of_birth=p.date_of_birth,
        )
        for p in results
    ]

    hint = (
        "Patient record found. Verify their identity before disclosing existing appointments."
        if summaries
        else "No patient record was found. Ask the caller if they have attended Grand Canal Dental Clinic previously."
    )

    return ToolResult(
        success=True,
        data=FindPatientData(patients=summaries, total_found=len(summaries)),
        hint=hint,
    )


# 2. check_availability
@router.post("/check_availability", response_model=ToolResult[CheckAvailabilityData])
async def check_availability(
    payload: CheckAvailabilityRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[CheckAvailabilityData]:
    """Search for free, bookable slots for a specific dental procedure within a date window."""
    # Find service
    service_res = await session.execute(
        select(Service).where(
            func.upper(Service.code) == payload.service_code.upper(), Service.is_active.is_(True)
        )
    )
    service = service_res.scalar_one_or_none()
    if not service:
        return ToolResult(
            success=False,
            error_code="INVALID_SERVICE_CODE",
            error_message=f"Service '{payload.service_code}' does not exist.",
            hint="Available service codes are: CHECKUP, HYGIENE, FILLING, EMERGENCY, EXTRACTION, ROOT_CANAL.",
        )

    dentist_id = payload.dentist_id
    if not dentist_id and payload.dentist_name:
        d_res = await session.execute(
            select(Dentist).where(Dentist.name.ilike(f"%{payload.dentist_name}%"))
        )
        matched_dentist = d_res.scalar_one_or_none()
        if matched_dentist:
            dentist_id = matched_dentist.id

    slots = await get_available_slots(
        session=session,
        start_date=payload.start_date,
        end_date=payload.end_date,
        service_id=service.id,
        dentist_id=dentist_id,
    )

    slot_summaries = [
        SlotSummary(
            dentist_id=s.dentist_id,
            dentist_name=s.dentist_name,
            service_code=service.code,
            start_time_local=format_dublin(s.start_time_local, "%A, %d %B %Y at %H:%M"),
            start_time_utc=s.start_time_utc,
            end_time_local=format_dublin(s.end_time_local, "%H:%M"),
            clinical_duration_minutes=s.clinical_duration_minutes,
            buffer_minutes=s.buffer_minutes,
        )
        for s in slots
    ]

    hint = (
        f"Found {len(slot_summaries)} available slots. Present 2 or 3 distinct options to the caller."
        if slot_summaries
        else "No slots are available on those dates. Suggest alternative days or offer to check the following week."
    )

    return ToolResult(
        success=True,
        data=CheckAvailabilityData(
            service_code=service.code,
            service_name=service.name,
            price_eur=service.price_eur,
            slots=slot_summaries,
            total_slots_available=len(slot_summaries),
        ),
        hint=hint,
    )


# 3. hold_slot
@router.post("/hold_slot", response_model=ToolResult[HoldSlotData])
async def hold_slot_endpoint(
    payload: HoldSlotRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[HoldSlotData]:
    """Hold a prospective slot for 2 minutes while collecting patient information."""
    service_res = await session.execute(
        select(Service).where(func.upper(Service.code) == payload.service_code.upper())
    )
    service = service_res.scalar_one_or_none()
    if not service:
        return ToolResult(
            success=False,
            error_code="INVALID_SERVICE_CODE",
            error_message=f"Service '{payload.service_code}' not found.",
            hint="Use one of: CHECKUP, HYGIENE, FILLING, EMERGENCY, EXTRACTION, ROOT_CANAL.",
        )

    try:
        hold = await hold_slot(
            session=session,
            dentist_id=payload.dentist_id,
            service_id=service.id,
            start_time_utc=payload.start_time_utc,
            patient_id=payload.patient_id,
            hold_duration_seconds=120,
        )
        await session.commit()
    except SlotUnavailableError as exc:
        return ToolResult(
            success=False,
            error_code="SLOT_UNAVAILABLE",
            error_message=str(exc),
            hint="This slot has already been taken. Call check_availability to locate another opening.",
        )

    return ToolResult(
        success=True,
        data=HoldSlotData(
            hold_id=hold.id,
            dentist_id=hold.dentist_id,
            service_code=service.code,
            start_time_local=format_dublin(to_dublin(hold.start_time_utc), "%A, %d %B at %H:%M"),
            start_time_utc=hold.start_time_utc,
            held_until_utc=hold.held_until_utc,
            hold_duration_seconds=120,
        ),
        hint="Slot held for 2 minutes. Now collect caller full name and phone number to finalize booking.",
    )


# 4. book_appointment
@router.post("/book_appointment", response_model=ToolResult[BookAppointmentData])
async def book_appointment_endpoint(
    payload: BookAppointmentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[BookAppointmentData]:
    """Confirm and finalize a dental appointment reservation with idempotency protection."""
    # Check idempotency cache
    if idempotency_key:
        cached = idempotency_manager.get_record(idempotency_key)
        if cached:
            return ToolResult[BookAppointmentData].model_validate(cached.body)

    # Resolve clinic and service
    clinic_res = await session.execute(select(Clinic).limit(1))
    clinic = clinic_res.scalar_one_or_none()
    if not clinic:
        return ToolResult(
            success=False,
            error_code="CLINIC_NOT_CONFIGURED",
            error_message="Clinic practice record is missing in database.",
            hint="Run the seed script 'data/seed.py' to initialize clinic records.",
        )

    service_res = await session.execute(
        select(Service).where(func.upper(Service.code) == payload.service_code.upper())
    )
    service = service_res.scalar_one_or_none()
    if not service:
        return ToolResult(
            success=False,
            error_code="INVALID_SERVICE_CODE",
            error_message=f"Service '{payload.service_code}' is invalid.",
            hint="Use one of the official clinic service codes.",
        )

    dentist_res = await session.execute(select(Dentist).where(Dentist.id == payload.dentist_id))
    dentist = dentist_res.scalar_one_or_none()
    if not dentist:
        return ToolResult(
            success=False,
            error_code="DENTIST_NOT_FOUND",
            error_message="Specified dentist does not exist.",
            hint="Pass a valid dentist UUID from check_availability.",
        )

    try:
        appointment = await book_appointment(
            session=session,
            clinic_id=clinic.id,
            patient_id=payload.patient_id,
            dentist_id=payload.dentist_id,
            service_id=service.id,
            start_time_utc=payload.start_time_utc,
            hold_id=payload.hold_id,
            notes=payload.notes,
        )
        await session.commit()
    except (SlotUnavailableError, HoldExpiredError) as exc:
        error_code = "HOLD_EXPIRED" if isinstance(exc, HoldExpiredError) else "SLOT_UNAVAILABLE"
        return ToolResult(
            success=False,
            error_code=error_code,
            error_message=str(exc),
            hint="The chosen time slot could not be secured. Check availability to choose a different time.",
        )

    response_data = BookAppointmentData(
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        dentist_name=dentist.name,
        service_name=service.name,
        price_eur=service.price_eur,
        start_time_local=format_dublin(
            to_dublin(appointment.start_time_utc), "%A, %d %B %Y at %H:%M"
        ),
        start_time_utc=appointment.start_time_utc,
        end_time_local=format_dublin(to_dublin(appointment.end_time_utc), "%H:%M"),
        status=appointment.status,
        clinic_phone=clinic.phone,
    )

    result = ToolResult(
        success=True,
        data=response_data,
        hint="Appointment successfully booked! Read the date, time, dentist name, and price back to caller to confirm.",
    )

    if idempotency_key:
        idempotency_manager.save_record(idempotency_key, 200, result.model_dump(mode="json"))

    return result


# 5. reschedule_appointment
@router.post("/reschedule_appointment", response_model=ToolResult[RescheduleAppointmentData])
async def reschedule_appointment_endpoint(
    payload: RescheduleAppointmentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[RescheduleAppointmentData]:
    """Reschedule an existing appointment to a new slot with 24h cancellation notice auditing."""
    if idempotency_key:
        cached = idempotency_manager.get_record(idempotency_key)
        if cached:
            return ToolResult[RescheduleAppointmentData].model_validate(cached.body)

    try:
        new_appt, is_late = await reschedule_appointment(
            session=session,
            appointment_id=payload.appointment_id,
            new_dentist_id=payload.new_dentist_id,
            new_start_time_utc=payload.new_start_time_utc,
        )
        await session.commit()
    except AppointmentNotFoundError:
        return ToolResult(
            success=False,
            error_code="APPOINTMENT_NOT_FOUND",
            error_message=f"Appointment {payload.appointment_id} does not exist.",
            hint="Verify the caller's identity and look up their active appointment ID first.",
        )
    except SlotUnavailableError as exc:
        return ToolResult(
            success=False,
            error_code="SLOT_UNAVAILABLE",
            error_message=str(exc),
            hint="The newly requested slot is unavailable. Run check_availability to locate open slots.",
        )

    # Fetch dentist and service names
    dentist_res = await session.execute(select(Dentist).where(Dentist.id == new_appt.dentist_id))
    dentist = dentist_res.scalar_one()
    srv_res = await session.execute(select(Service).where(Service.id == new_appt.service_id))
    service = srv_res.scalar_one()

    policy_notice = (
        "Notice: Rescheduled within 24 hours of original booking. €30 late change fee recorded on account."
        if is_late
        else "Rescheduled with more than 24 hours notice. No cancellation or rescheduling fee applied."
    )

    data = RescheduleAppointmentData(
        new_appointment_id=new_appt.id,
        old_appointment_id=payload.appointment_id,
        dentist_name=dentist.name,
        service_name=service.name,
        start_time_local=format_dublin(to_dublin(new_appt.start_time_utc), "%A, %d %B %Y at %H:%M"),
        start_time_utc=new_appt.start_time_utc,
        is_late_reschedule=is_late,
        policy_notice=policy_notice,
    )

    result = ToolResult(
        success=True,
        data=data,
        hint=f"Appointment rescheduled successfully. {policy_notice}",
    )

    if idempotency_key:
        idempotency_manager.save_record(idempotency_key, 200, result.model_dump(mode="json"))

    return result


# 6. cancel_appointment
@router.post("/cancel_appointment", response_model=ToolResult[CancelAppointmentData])
async def cancel_appointment_endpoint(
    payload: CancelAppointmentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[CancelAppointmentData]:
    """Cancel an appointment and evaluate the 24-hour notice rule."""
    if idempotency_key:
        cached = idempotency_manager.get_record(idempotency_key)
        if cached:
            return ToolResult[CancelAppointmentData].model_validate(cached.body)

    try:
        appt, is_late = await cancel_appointment(
            session=session,
            appointment_id=payload.appointment_id,
            reason=payload.reason,
        )
        await session.commit()
    except AppointmentNotFoundError:
        return ToolResult(
            success=False,
            error_code="APPOINTMENT_NOT_FOUND",
            error_message="Appointment not found.",
            hint="Check the appointment ID before calling cancel_appointment.",
        )
    except AppointmentAlreadyCancelledError:
        return ToolResult(
            success=False,
            error_code="ALREADY_CANCELLED",
            error_message="This appointment has already been cancelled.",
            hint="Inform the caller that their appointment was already cancelled previously.",
        )

    fee = Decimal("30.00") if is_late else Decimal("0.00")
    policy_notice = (
        "Cancelled with less than 24 hours notice. A €30 late cancellation fee applies."
        if is_late
        else "Cancelled with 24 hours or more notice. No cancellation fee applies."
    )

    data = CancelAppointmentData(
        appointment_id=appt.id,
        status=appt.status,
        is_late_cancellation=is_late,
        policy_fee_incurred_eur=fee,
        policy_notice=policy_notice,
    )

    result = ToolResult(
        success=True,
        data=data,
        hint=f"Appointment cancelled. {policy_notice}",
    )

    if idempotency_key:
        idempotency_manager.save_record(idempotency_key, 200, result.model_dump(mode="json"))

    return result


# 7. get_clinic_info
@router.get("/get_clinic_info", response_model=ToolResult[ClinicInfoData])
async def get_clinic_info(
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[ClinicInfoData]:
    """Retrieve official clinic operating hours, dentist profiles, services, fees, and policies."""
    clinic_res = await session.execute(
        select(Clinic).options(selectinload(Clinic.dentists), selectinload(Clinic.services))
    )
    clinic = clinic_res.scalars().first()

    if not clinic:
        # Fallback to config spec values
        return ToolResult(
            success=True,
            data=ClinicInfoData(
                clinic_name="Grand Canal Dental Clinic",
                address="12 Grand Canal Quay, Dublin 2, D02 X2Y8",
                phone="+35312345678",
                emergency_phone="+35312349999",
                timezone="Europe/Dublin",
                opening_hours={
                    "Monday": "08:30 - 18:00 (Lunch 13:00 - 14:00)",
                    "Tuesday": "08:30 - 18:00 (Lunch 13:00 - 14:00)",
                    "Wednesday": "08:30 - 18:00 (Lunch 13:00 - 14:00)",
                    "Thursday": "08:30 - 18:00 (Lunch 13:00 - 14:00)",
                    "Friday": "08:30 - 17:00 (Lunch 13:00 - 14:00)",
                    "Saturday": "09:00 - 14:00 (Emergency & Hygiene only)",
                    "Sunday": "Closed (Emergency divert only)",
                },
                dentists=[],
                services=[],
                cancellation_policy="Minimum 24 hours notice required. €30 late cancellation fee applies within 24 hours.",
                emergency_policy="Immediate triage for severe facial swelling, uncontrolled bleeding, or knocked-out adult tooth.",
            ),
        )

    # Load dentists with working hours
    dentists_res = await session.execute(
        select(Dentist).options(selectinload(Dentist.working_hours))
    )
    dentists = list(dentists_res.scalars().all())

    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dentists_info = [
        DentistInfo(
            dentist_id=d.id,
            name=d.name,
            specialisms=d.specialisms,
            working_days=[day_names[w.day_of_week] for w in d.working_hours if w.is_working],
        )
        for d in dentists
    ]

    services_res = await session.execute(select(Service).where(Service.is_active.is_(True)))
    services = list(services_res.scalars().all())

    services_info = [
        ServiceInfo(
            code=s.code,
            name=s.name,
            duration_minutes=s.duration_minutes,
            buffer_minutes=s.buffer_minutes,
            price_eur=s.price_eur,
            description=s.description,
        )
        for s in services
    ]

    opening_hours_map = {
        "Monday": "08:30 - 18:00 (Lunch 13:00 - 14:00)",
        "Tuesday": "08:30 - 18:00 (Lunch 13:00 - 14:00)",
        "Wednesday": "08:30 - 18:00 (Lunch 13:00 - 14:00)",
        "Thursday": "08:30 - 18:00 (Lunch 13:00 - 14:00)",
        "Friday": "08:30 - 17:00 (Lunch 13:00 - 14:00)",
        "Saturday": "09:00 - 14:00 (Emergency & Hygiene only)",
        "Sunday": "Closed (Emergency divert only)",
    }

    return ToolResult(
        success=True,
        data=ClinicInfoData(
            clinic_name=clinic.name,
            address="12 Grand Canal Quay, Dublin 2, D02 X2Y8, Ireland",
            phone=clinic.phone,
            emergency_phone=clinic.emergency_phone,
            timezone=clinic.timezone,
            opening_hours=opening_hours_map,
            dentists=dentists_info,
            services=services_info,
            cancellation_policy="Minimum 24 hours notice required. Cancellations under 24 hours incur a €30 late fee.",
            emergency_policy="Immediate escalation for uncontrolled bleeding, airway swelling, or knocked-out adult teeth.",
        ),
        hint="Share opening hours, dentist specialties, or transparent pricing as requested by the caller.",
    )


# 8. take_message
@router.post("/take_message", response_model=ToolResult[TakeMessageData])
async def take_message(
    payload: TakeMessageRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[TakeMessageData]:
    """Log a caller message or callback request when clinic is closed or lines are busy."""
    clinic_res = await session.execute(select(Clinic).limit(1))
    clinic = clinic_res.scalar_one_or_none()
    clinic_id = clinic.id if clinic else uuid.uuid4()

    call_log = CallLog(
        clinic_id=clinic_id,
        caller_phone=payload.caller_phone,
        direction="INBOUND",
        status="VOICEMAIL",
        transcript_redacted=f"From: {payload.caller_name} | Phone: {payload.caller_phone} | Urgency: {payload.urgency} | Message: {payload.message}",
        summary=f"Callback message from {payload.caller_name} ({payload.urgency})",
    )
    session.add(call_log)
    await session.commit()

    promise = (
        "Your urgent message has been flagged for our on-call dental team."
        if payload.urgency.upper() == "URGENT"
        else "Your message has been logged. Our reception team will return your call when the clinic opens."
    )

    return ToolResult(
        success=True,
        data=TakeMessageData(message_id=call_log.id, status="LOGGED", callback_promise=promise),
        hint="Inform the caller that their message has been recorded and reception will call back shortly.",
    )


# 9. transfer_to_human
@router.post("/transfer_to_human", response_model=ToolResult[TransferToHumanData])
async def transfer_to_human(
    payload: TransferToHumanRequest,
    session: AsyncSession = Depends(get_async_session),
) -> ToolResult[TransferToHumanData]:
    """Initiate an immediate call transfer to human receptionist or emergency dental surgeon."""
    is_emergency = "EMERGENCY" in payload.reason.upper()
    target_number = settings.clinic_emergency_phone if is_emergency else settings.clinic_phone

    clinic_res = await session.execute(select(Clinic).limit(1))
    clinic = clinic_res.scalar_one_or_none()
    clinic_id = clinic.id if clinic else uuid.uuid4()

    call_log = CallLog(
        clinic_id=clinic_id,
        caller_phone=payload.caller_phone,
        patient_id=payload.patient_id,
        direction="INBOUND",
        status="TRANSFERRED",
        summary=f"Transferred to {target_number} (Reason: {payload.reason})",
    )
    session.add(call_log)
    await session.commit()

    spoken_notice = (
        "I am connecting you immediately to our emergency duty dentist. Please hold the line."
        if is_emergency
        else "I am transferring you to our clinic reception team now. Please stay on the line."
    )

    return ToolResult(
        success=True,
        data=TransferToHumanData(
            target_phone=target_number,
            reason=payload.reason,
            spoken_notice_for_caller=spoken_notice,
        ),
        hint="Speak the transfer notice to the caller, then execute telephony SIP transfer.",
    )
