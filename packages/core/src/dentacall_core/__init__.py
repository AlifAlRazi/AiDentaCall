"""DentaCall Core Package - Domain models, availability engine, and booking services."""

from dentacall_core.availability import (
    TimeSlot,
    compute_free_slots_for_dentist_day,
    get_available_slots,
)
from dentacall_core.booking import (
    AppointmentAlreadyCancelledError,
    AppointmentNotFoundError,
    BookingError,
    HoldExpiredError,
    SlotUnavailableError,
    book_appointment,
    cancel_appointment,
    hold_slot,
    release_hold,
    reschedule_appointment,
)
from dentacall_core.config import ClinicConfig
from dentacall_core.db import (
    AsyncSessionLocal,
    SyncSessionLocal,
    async_engine,
    get_async_session,
    init_db,
    sync_engine,
)
from dentacall_core.holidays import (
    get_irish_public_holiday_name,
    get_irish_public_holidays,
    is_irish_public_holiday,
)
from dentacall_core.models import (
    Appointment,
    AppointmentStatus,
    Base,
    CallLog,
    Clinic,
    Dentist,
    Patient,
    Service,
    SlotHold,
    SlotHoldStatus,
    TimeOff,
    WorkingHours,
)
from dentacall_core.settings import settings
from dentacall_core.timezone import (
    DUBLIN_TZ,
    UTC,
    combine_dublin,
    format_dublin,
    now_dublin,
    now_utc,
    to_dublin,
    to_utc,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ClinicConfig",
    "settings",
    "Base",
    "Clinic",
    "Dentist",
    "Service",
    "WorkingHours",
    "TimeOff",
    "Patient",
    "Appointment",
    "SlotHold",
    "CallLog",
    "AppointmentStatus",
    "SlotHoldStatus",
    "async_engine",
    "sync_engine",
    "AsyncSessionLocal",
    "SyncSessionLocal",
    "get_async_session",
    "init_db",
    "DUBLIN_TZ",
    "UTC",
    "to_utc",
    "to_dublin",
    "now_utc",
    "now_dublin",
    "format_dublin",
    "combine_dublin",
    "is_irish_public_holiday",
    "get_irish_public_holidays",
    "get_irish_public_holiday_name",
    "TimeSlot",
    "compute_free_slots_for_dentist_day",
    "get_available_slots",
    "hold_slot",
    "release_hold",
    "book_appointment",
    "cancel_appointment",
    "reschedule_appointment",
    "BookingError",
    "SlotUnavailableError",
    "HoldExpiredError",
    "AppointmentNotFoundError",
    "AppointmentAlreadyCancelledError",
]
