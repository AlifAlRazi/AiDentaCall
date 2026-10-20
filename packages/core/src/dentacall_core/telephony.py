"""Telephony session management, dropped call recovery, and spend cap enforcement."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dentacall_core.booking import release_hold
from dentacall_core.models import CallLog, Clinic
from dentacall_core.settings import settings
from dentacall_core.timezone import now_utc

logger = logging.getLogger(__name__)


@dataclass
class ActiveCallSession:
    """In-memory active telephony call session tracking."""

    call_id: str
    call_sid: str | None = None
    caller_phone: str | None = None
    patient_id: str | None = None
    patient_name: str | None = None
    active_holds: set[uuid.UUID] = field(default_factory=set)
    start_time_utc: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_dropped: bool = False
    is_completed: bool = False
    is_transferred: bool = False
    recording_url: str | None = None


class TelephonyManager:
    """Manages concurrent telephony calls, spend cap tracking, and dropped-call hold releases."""

    def __init__(self) -> None:
        self._active_sessions: dict[str, ActiveCallSession] = {}
        self._daily_spend_usd: dict[date, float] = {}
        # Cost per minute estimate: Twilio inbound ($0.014) + Deepgram ($0.0043) +
        # OpenAI ($0.015) + ElevenLabs ($0.025) + LiveKit ($0.004) ~= $0.06/min
        self.estimated_cost_per_minute_usd: float = 0.06

    def get_today_spend(self, target_date: date | None = None) -> float:
        """Get total estimated spend for today in Dublin date."""
        today = target_date or now_utc().date()
        return self._daily_spend_usd.get(today, 0.0)

    def add_spend(self, amount_usd: float, target_date: date | None = None) -> None:
        """Add to daily spend tracker."""
        today = target_date or now_utc().date()
        current = self._daily_spend_usd.get(today, 0.0)
        self._daily_spend_usd[today] = current + max(0.0, amount_usd)

    def is_spend_cap_exceeded(self) -> bool:
        """Check if today's estimated spend exceeds the daily spend cap."""
        return self.get_today_spend() >= settings.daily_spend_cap_usd

    def is_concurrency_limit_exceeded(self) -> bool:
        """Check if active concurrent calls exceed the maximum limit."""
        return len(self._active_sessions) >= settings.max_concurrent_calls

    def can_accept_call(self) -> tuple[bool, str | None]:
        """Check whether a new inbound call can be accepted under limit and cap rules."""
        if self.is_concurrency_limit_exceeded():
            logger.warning(
                f"Telephony concurrency limit reached: {len(self._active_sessions)}/{settings.max_concurrent_calls}"
            )
            return (
                False,
                "All lines are currently busy assisting other patients. Please hold or call back shortly.",
            )
        if self.is_spend_cap_exceeded():
            logger.warning(
                f"Telephony daily spend cap reached: ${self.get_today_spend():.2f}/${settings.daily_spend_cap_usd:.2f}"
            )
            return (
                False,
                "The clinic voice assistant has reached its daily quota. Please visit our website or call our main desk.",
            )
        return True, None

    def start_call_session(
        self,
        call_id: str,
        call_sid: str | None = None,
        caller_phone: str | None = None,
    ) -> ActiveCallSession:
        """Register a new active call session."""
        session = ActiveCallSession(
            call_id=call_id,
            call_sid=call_sid,
            caller_phone=caller_phone,
        )
        self._active_sessions[call_id] = session
        logger.info(
            f"Telephony session started: call_id={call_id}, call_sid={call_sid}, phone={caller_phone}"
        )
        return session

    def get_session(self, call_id: str) -> ActiveCallSession | None:
        """Retrieve active call session by call_id or call_sid."""
        if call_id in self._active_sessions:
            return self._active_sessions[call_id]
        # Fallback to search by call_sid
        for s in self._active_sessions.values():
            if s.call_sid == call_id:
                return s
        return None

    def register_call_hold(self, call_id: str, hold_id: uuid.UUID | str) -> None:
        """Associate an active slot hold with the calling session."""
        parsed_id = uuid.UUID(str(hold_id)) if isinstance(hold_id, str) else hold_id
        session = self.get_session(call_id)
        if session:
            session.active_holds.add(parsed_id)
            logger.info(f"Registered slot hold {parsed_id} for call {call_id}")

    def mark_hold_booked(self, call_id: str, hold_id: uuid.UUID | str) -> None:
        """Remove hold from active tracking once successfully converted to a booking."""
        parsed_id = uuid.UUID(str(hold_id)) if isinstance(hold_id, str) else hold_id
        session = self.get_session(call_id)
        if session and parsed_id in session.active_holds:
            session.active_holds.remove(parsed_id)
            logger.info(f"Slot hold {parsed_id} converted to booking for call {call_id}")

    async def handle_call_disconnect(
        self,
        call_id: str,
        db_session: AsyncSession | None = None,
        reason: str = "COMPLETED",
    ) -> dict[str, Any]:
        """Clean up call session on disconnect and immediately release any unbooked holds."""
        session = self.get_session(call_id)
        if not session:
            return {"call_id": call_id, "holds_released": 0, "status": "UNKNOWN"}

        duration_seconds = max(
            1.0,
            (datetime.now(UTC) - session.start_time_utc).total_seconds(),
        )
        cost_usd = (duration_seconds / 60.0) * self.estimated_cost_per_minute_usd
        self.add_spend(cost_usd)

        holds_released = 0
        released_hold_ids: list[str] = []

        # Release any stuck holds if call dropped or completed without booking
        if session.active_holds and db_session:
            for hold_id in list(session.active_holds):
                try:
                    success = await release_hold(db_session, hold_id)
                    if success:
                        holds_released += 1
                        released_hold_ids.append(str(hold_id))
                        logger.info(f"Released held slot {hold_id} on call disconnect ({reason})")
                except Exception as e:
                    logger.error(f"Error releasing hold {hold_id} on disconnect: {e}")
            await db_session.commit()

        # Log outcome in database if db_session available
        if db_session:
            try:
                clinic_res = await db_session.execute(select(Clinic.id).limit(1))
                clinic_id = clinic_res.scalar_one_or_none()
                if clinic_id:
                    call_log = CallLog(
                        clinic_id=clinic_id,
                        call_sid=session.call_sid,
                        caller_phone=session.caller_phone,
                        direction="INBOUND",
                        status="DROPPED" if (reason == "DROPPED" or holds_released > 0) else reason,
                        summary=(
                            f"Call {reason.lower()}. Duration: {int(duration_seconds)}s. "
                            f"Holds released: {holds_released}."
                        ),
                    )
                    db_session.add(call_log)
                    await db_session.commit()
            except Exception as e:
                logger.warning(f"Could not persist call log on disconnect: {e}")

        # Remove from active calls
        self._active_sessions.pop(call_id, None)
        if session.call_sid and session.call_sid in self._active_sessions:
            self._active_sessions.pop(session.call_sid, None)

        logger.info(
            f"Telephony session ended: call_id={call_id}, duration={int(duration_seconds)}s, "
            f"holds_released={holds_released}, cost=${cost_usd:.4f}"
        )

        return {
            "call_id": call_id,
            "call_sid": session.call_sid,
            "duration_seconds": duration_seconds,
            "holds_released": holds_released,
            "released_hold_ids": released_hold_ids,
            "estimated_cost_usd": cost_usd,
            "status": "DROPPED" if holds_released > 0 else reason,
        }

    def clear(self) -> None:
        """Reset state for tests."""
        self._active_sessions.clear()
        self._daily_spend_usd.clear()


# Global singleton instance
telephony_manager = TelephonyManager()
