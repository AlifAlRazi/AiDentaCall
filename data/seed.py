"""Seed script for populating fake clinic data, rosters, services, holidays, and sample appointments."""

import asyncio
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from dentacall_core.db import AsyncSessionLocal, init_db
from dentacall_core.holidays import get_irish_public_holidays
from dentacall_core.models import (
    Appointment,
    AppointmentStatus,
    Clinic,
    Dentist,
    Patient,
    Service,
    TimeOff,
    WorkingHours,
)
from dentacall_core.timezone import DUBLIN_TZ, to_utc
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_database(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Populate database with Grand Canal Dental Clinic data matching docs/spec.md."""
    # Clean existing data in reverse FK order
    await session.execute(delete(Appointment))
    await session.execute(delete(TimeOff))
    await session.execute(delete(WorkingHours))
    await session.execute(delete(Service))
    await session.execute(delete(Dentist))
    await session.execute(delete(Patient))
    await session.execute(delete(Clinic))
    await session.flush()

    # 1. Create Clinic
    clinic = Clinic(
        id=uuid.uuid4(),
        name="Grand Canal Dental Clinic",
        timezone="Europe/Dublin",
        phone="+35312345678",
        email="reception@grandcanaldental.ie",
        emergency_phone="+35312349999",
        cancellation_notice_hours=24,
    )
    session.add(clinic)
    await session.flush()

    # 2. Create 3 Dentists
    dr_sean = Dentist(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        name="Dr. Sean O'Connor",
        registration_number="IE-DEN-44821",
        specialisms="Lead General Dentist, Preventative & Restorative",
        email="dr.sean@grandcanaldental.ie",
        phone="+353871112233",
        is_active=True,
    )
    dr_aoife = Dentist(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        name="Dr. Aoife Murphy",
        registration_number="IE-DEN-51209",
        specialisms="Associate Dentist, Paediatric & Aesthetic Restorations",
        email="dr.aoife@grandcanaldental.ie",
        phone="+353872223344",
        is_active=True,
    )
    dr_liam = Dentist(
        id=uuid.uuid4(),
        clinic_id=clinic.id,
        name="Dr. Liam Kelly",
        registration_number="IE-DEN-39744",
        specialisms="Senior Dental Surgeon, Endodontics & Oral Surgery",
        email="dr.liam@grandcanaldental.ie",
        phone="+353873334455",
        is_active=True,
    )
    session.add_all([dr_sean, dr_aoife, dr_liam])
    await session.flush()

    # 3. Create Working Hours / Rosters
    # Dr. Sean: Mon-Thu (08:30 - 17:30), lunch 13:00 - 14:00
    for day_idx in [0, 1, 2, 3]:  # Mon, Tue, Wed, Thu
        session.add(
            WorkingHours(
                dentist_id=dr_sean.id,
                day_of_week=day_idx,
                start_time=time(8, 30),
                end_time=time(17, 30),
                break_start_time=time(13, 0),
                break_end_time=time(14, 0),
                is_working=True,
            )
        )

    # Dr. Aoife: Tue-Fri (08:30 - 17:00, lunch 13:00-14:00), Sat (09:00 - 14:00, no lunch)
    for day_idx in [1, 2, 3, 4]:  # Tue, Wed, Thu, Fri
        session.add(
            WorkingHours(
                dentist_id=dr_aoife.id,
                day_of_week=day_idx,
                start_time=time(8, 30),
                end_time=time(17, 0),
                break_start_time=time(13, 0),
                break_end_time=time(14, 0),
                is_working=True,
            )
        )
    session.add(
        WorkingHours(
            dentist_id=dr_aoife.id,
            day_of_week=5,  # Saturday
            start_time=time(9, 0),
            end_time=time(14, 0),
            break_start_time=None,
            break_end_time=None,
            is_working=True,
        )
    )

    # Dr. Liam: Mon, Wed, Fri (08:30 - 17:30, lunch 13:00-14:00), Sat (09:00 - 14:00 emergency)
    for day_idx in [0, 2, 4]:  # Mon, Wed, Fri
        session.add(
            WorkingHours(
                dentist_id=dr_liam.id,
                day_of_week=day_idx,
                start_time=time(8, 30),
                end_time=time(17, 30),
                break_start_time=time(13, 0),
                break_end_time=time(14, 0),
                is_working=True,
            )
        )
    session.add(
        WorkingHours(
            dentist_id=dr_liam.id,
            day_of_week=5,  # Saturday
            start_time=time(9, 0),
            end_time=time(14, 0),
            break_start_time=None,
            break_end_time=None,
            is_working=True,
        )
    )
    await session.flush()

    # 4. Create 6 Services
    services_data = [
        (
            "CHECKUP",
            "Routine Dental Examination",
            30,
            5,
            Decimal("65.00"),
            "Comprehensive checkup and assessment.",
        ),
        (
            "HYGIENE",
            "Scale & Polish (Hygiene)",
            45,
            5,
            Decimal("90.00"),
            "Ultrasonic dental cleaning and polishing.",
        ),
        (
            "FILLING",
            "Composite (White) Filling",
            45,
            10,
            Decimal("130.00"),
            "Tooth-colored aesthetic resin restoration.",
        ),
        (
            "EMERGENCY",
            "Emergency Pain & Trauma Assessment",
            30,
            5,
            Decimal("80.00"),
            "Acute symptom diagnosis and pain relief.",
        ),
        (
            "EXTRACTION",
            "Simple Tooth Extraction",
            45,
            15,
            Decimal("140.00"),
            "Non-surgical extraction with anaesthetic.",
        ),
        (
            "ROOT_CANAL",
            "Root Canal Consult & Stage 1",
            60,
            15,
            Decimal("220.00"),
            "Pulp extirpation and canal disinfection.",
        ),
    ]
    services_map: dict[str, Service] = {}
    for code, name, dur, buf, price, desc in services_data:
        srv = Service(
            id=uuid.uuid4(),
            clinic_id=clinic.id,
            code=code,
            name=name,
            duration_minutes=dur,
            buffer_minutes=buf,
            price_eur=price,
            description=desc,
            is_active=True,
        )
        session.add(srv)
        services_map[code] = srv
    await session.flush()

    # 5. Irish Public Holidays recorded as clinic-wide TimeOff
    current_year = date.today().year
    holidays = get_irish_public_holidays(current_year)
    for holiday_date, holiday_name in holidays.items():
        h_start = datetime.combine(holiday_date, time.min, tzinfo=DUBLIN_TZ)
        h_end = datetime.combine(holiday_date, time.max, tzinfo=DUBLIN_TZ)
        session.add(
            TimeOff(
                dentist_id=None,
                start_time_utc=to_utc(h_start),
                end_time_utc=to_utc(h_end),
                reason=f"Irish Public Holiday: {holiday_name}",
            )
        )
    await session.flush()

    # 6. Sample Patients
    patients_data = [
        ("Conor", "Walsh", "+353871234001", "conor.walsh@example.ie", date(1985, 4, 12)),
        ("Siobhan", "Byrne", "+353862345002", "siobhan.byrne@example.ie", date(1992, 8, 24)),
        ("Patrick", "McCarthy", "+353853456003", "patrick.mccarthy@example.ie", date(1978, 11, 3)),
        ("Ciara", "O'Sullivan", "+353874567004", "ciara.osullivan@example.ie", date(1996, 2, 19)),
        ("Liam", "Gallagher", "+353865678005", "liam.gallagher@example.ie", date(1990, 7, 15)),
    ]
    patients: list[Patient] = []
    for first, last, phone, email, dob in patients_data:
        p = Patient(
            id=uuid.uuid4(),
            first_name=first,
            last_name=last,
            phone=phone,
            email=email,
            date_of_birth=dob,
        )
        session.add(p)
        patients.append(p)
    await session.flush()

    # 7. Sample Already-Booked Appointments
    # Find next Monday that is not a holiday
    base_date = date.today() + timedelta(days=1)
    while base_date.weekday() != 0 or base_date in holidays:
        base_date += timedelta(days=1)

    # Book Dr. Sean Monday at 09:00 (Checkup: 30m + 5m buffer)
    appt1_start = datetime.combine(base_date, time(9, 0), tzinfo=DUBLIN_TZ)
    appt1_end = appt1_start + timedelta(minutes=35)
    session.add(
        Appointment(
            clinic_id=clinic.id,
            patient_id=patients[0].id,
            dentist_id=dr_sean.id,
            service_id=services_map["CHECKUP"].id,
            start_time_utc=to_utc(appt1_start),
            end_time_utc=to_utc(appt1_end),
            clinical_duration_minutes=30,
            buffer_duration_minutes=5,
            status=AppointmentStatus.CONFIRMED.value,
            notes="Routine annual dental checkup.",
        )
    )

    # Book Dr. Aoife Tuesday at 10:00 (Hygiene: 45m + 5m buffer)
    tuesday_date = base_date + timedelta(days=1)
    appt2_start = datetime.combine(tuesday_date, time(10, 0), tzinfo=DUBLIN_TZ)
    appt2_end = appt2_start + timedelta(minutes=50)
    session.add(
        Appointment(
            clinic_id=clinic.id,
            patient_id=patients[1].id,
            dentist_id=dr_aoife.id,
            service_id=services_map["HYGIENE"].id,
            start_time_utc=to_utc(appt2_start),
            end_time_utc=to_utc(appt2_end),
            clinical_duration_minutes=45,
            buffer_duration_minutes=5,
            status=AppointmentStatus.CONFIRMED.value,
            notes="Scale & Polish clean.",
        )
    )

    # Book Dr. Liam Wednesday at 11:00 (Root Canal Stage 1: 60m + 15m buffer)
    wed_date = base_date + timedelta(days=2)
    appt3_start = datetime.combine(wed_date, time(11, 0), tzinfo=DUBLIN_TZ)
    appt3_end = appt3_start + timedelta(minutes=75)
    session.add(
        Appointment(
            clinic_id=clinic.id,
            patient_id=patients[2].id,
            dentist_id=dr_liam.id,
            service_id=services_map["ROOT_CANAL"].id,
            start_time_utc=to_utc(appt3_start),
            end_time_utc=to_utc(appt3_end),
            clinical_duration_minutes=60,
            buffer_duration_minutes=15,
            status=AppointmentStatus.CONFIRMED.value,
            notes="Extirpation stage 1.",
        )
    )

    await session.commit()
    print(
        "Seed complete: Clinic, Dentists, Services, Rosters, Holidays, Patients, and Bookings loaded."
    )
    return {
        "clinic_id": clinic.id,
        "dr_sean_id": dr_sean.id,
        "dr_aoife_id": dr_aoife.id,
        "dr_liam_id": dr_liam.id,
        "checkup_service_id": services_map["CHECKUP"].id,
        "hygiene_service_id": services_map["HYGIENE"].id,
    }


async def main() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_database(session)


if __name__ == "__main__":
    asyncio.run(main())
