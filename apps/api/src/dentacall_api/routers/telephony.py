"""Twilio Telephony Webhook Router for inbound calls, SIP bridging, dropped calls, and transfers."""

import logging
import uuid
from typing import Any

import phonenumbers
from dentacall_core.db import get_async_session
from dentacall_core.settings import settings
from dentacall_core.telephony import telephony_manager
from fastapi import APIRouter, Depends, Form, Header, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from twilio.twiml.voice_response import Dial, VoiceResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telephony", tags=["Telephony"])


class RegisterHoldRequest(BaseModel):
    """Payload to associate a slot hold with an active telephony call."""

    call_id: str
    hold_id: str


class MarkBookedRequest(BaseModel):
    """Payload to confirm a slot hold has been successfully booked."""

    call_id: str
    hold_id: str


def normalize_phone(raw_phone: str | None) -> str | None:
    """Normalize phone number to E.164 using libphonenumber with IE default region."""
    if not raw_phone:
        return None
    try:
        parsed = phonenumbers.parse(raw_phone, "IE")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass
    return raw_phone


def verify_twilio_signature(
    request: Request,
    x_twilio_signature: str | None = Header(None, alias="X-Twilio-Signature"),
) -> bool:
    """Validate Twilio request signature if auth token is configured."""
    if not settings.twilio_auth_token or not x_twilio_signature:
        return True

    from twilio.request_validator import RequestValidator

    validator = RequestValidator(settings.twilio_auth_token)
    # Validate against request URL if signature present
    return bool(validator.validate(str(request.url), {}, x_twilio_signature))


@router.post("/twilio/incoming")
async def twilio_incoming_call(
    request: Request,
    CallSid: str = Form(default_factory=lambda: str(uuid.uuid4())),
    From: str | None = Form(None),
    To: str | None = Form(None),
) -> Response:
    """Handle incoming Twilio voice webhook and bridge to AI receptionist with legal disclosure."""
    caller_phone = normalize_phone(From)
    logger.info(f"Incoming Twilio phone call: CallSid={CallSid}, From={caller_phone}, To={To}")

    # 1. Enforce Concurrency and Spend Cap
    allowed, rejection_reason = telephony_manager.can_accept_call()
    response = VoiceResponse()

    if not allowed:
        response.say(
            rejection_reason
            or "The clinic voice line is currently unavailable. Please call back later.",
            voice="Polly.Emily",
        )
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # 2. Register Active Call Session
    telephony_manager.start_call_session(
        call_id=CallSid,
        call_sid=CallSid,
        caller_phone=caller_phone,
    )

    # 3. Mandatory AI Receptionist & Call Recording Disclosure
    if settings.call_recording_notice_enabled:
        response.say(
            "Thank you for calling Grand Canal Dental Clinic. "
            "Please note that this call is handled by an AI receptionist and may be recorded "
            "for quality and training purposes.",
            voice="Polly.Emily",
        )

    # 4. Bridge to LiveKit SIP Trunk or SIP URI
    sip_uri = settings.livekit_sip_uri or (
        f"sip:{CallSid}@sip.livekit.cloud" if settings.livekit_url else None
    )

    if sip_uri:
        dial = Dial(
            timeout=30,
            action=f"{settings.api_base_url}/api/telephony/twilio/status",
            method="POST",
        )
        dial.sip(sip_uri)
        response.append(dial)
    else:
        # Fallback interactive prompt if SIP trunking is not yet active on local dev
        response.say(
            "Connecting you to the clinic scheduling service. How can I help you today?",
            voice="Polly.Emily",
        )

    return Response(content=str(response), media_type="application/xml")


@router.post("/twilio/status")
async def twilio_call_status(
    CallSid: str = Form(...),
    CallStatus: str = Form("completed"),
    CallDuration: str | None = Form(None),
    db: AsyncSession = Depends(get_async_session),
) -> Response:
    """Handle Twilio call status callbacks; clean up dropped calls and release stuck slot holds."""
    logger.info(
        f"Twilio status callback: CallSid={CallSid}, status={CallStatus}, duration={CallDuration}s"
    )

    terminal_statuses = {"completed", "canceled", "failed", "busy", "no-answer"}
    if CallStatus.lower() in terminal_statuses:
        reason = "DROPPED" if CallStatus.lower() in {"failed", "canceled"} else CallStatus.upper()
        result = await telephony_manager.handle_call_disconnect(
            call_id=CallSid,
            db_session=db,
            reason=reason,
        )
        logger.info(
            f"Processed disconnect for {CallSid}: holds_released={result['holds_released']}"
        )

    response = VoiceResponse()
    return Response(content=str(response), media_type="application/xml")


@router.post("/twilio/transfer")
async def twilio_transfer_call(
    reason: str = Form("REQUESTED_BY_PATIENT"),
    target_number: str | None = Form(None),
) -> Response:
    """Transfer call to a human receptionist or emergency line."""
    response = VoiceResponse()

    if reason.upper() == "EMERGENCY":
        dest_number = target_number or settings.emergency_transfer_number
        response.say(
            "Transferring your call immediately to our emergency duty staff. Please stay on the line.",
            voice="Polly.Emily",
        )
    else:
        dest_number = target_number or settings.clinic_escalation_number
        response.say(
            "Transferring you to a clinic receptionist now. Please hold.",
            voice="Polly.Emily",
        )

    dial = Dial(
        timeout=20,
        action="/api/telephony/twilio/dial-status",
        method="POST",
    )
    dial.number(dest_number)
    response.append(dial)

    return Response(content=str(response), media_type="application/xml")


@router.post("/twilio/dial-status")
async def twilio_dial_status(
    DialCallStatus: str = Form("completed"),
) -> Response:
    """Handle transfer dial outcome; fallback to voicemail if no human answers."""
    logger.info(f"Twilio dial status result: DialCallStatus={DialCallStatus}")
    response = VoiceResponse()

    # If call was answered by human, hang up cleanly when conversation ends
    if DialCallStatus.lower() in {"completed", "answered"}:
        response.hangup()
        return Response(content=str(response), media_type="application/xml")

    # If unanswered, busy, or failed: transition to Voicemail
    response.say(
        "Nobody is currently available to take your call. "
        "Please leave your name, phone number, and a brief message after the tone.",
        voice="Polly.Emily",
    )
    response.record(
        action="/api/telephony/twilio/voicemail",
        max_length=120,
        play_beep=True,
        transcribe=False,
    )
    response.say("We did not receive your message. Goodbye.", voice="Polly.Emily")
    response.hangup()

    return Response(content=str(response), media_type="application/xml")


@router.post("/twilio/voicemail")
async def twilio_voicemail_recorded(
    CallSid: str = Form(...),
    From: str | None = Form(None),
    RecordingUrl: str | None = Form(None),
    RecordingDuration: str | None = Form(None),
) -> Response:
    """Record patient voicemail callback message."""
    logger.info(
        f"Voicemail recorded: CallSid={CallSid}, From={From}, duration={RecordingDuration}s, URL={RecordingUrl}"
    )

    session = telephony_manager.get_session(CallSid)
    if session:
        session.recording_url = RecordingUrl

    response = VoiceResponse()
    response.say(
        "Thank you. Your message has been recorded and a clinic receptionist will call you back shortly. Goodbye.",
        voice="Polly.Emily",
    )
    response.hangup()

    return Response(content=str(response), media_type="application/xml")


@router.post("/hold")
async def register_active_hold(payload: RegisterHoldRequest) -> dict[str, Any]:
    """Internal endpoint for agent to register slot hold against active call session."""
    telephony_manager.register_call_hold(payload.call_id, payload.hold_id)
    return {"status": "ok", "call_id": payload.call_id, "hold_id": payload.hold_id}


@router.post("/booked")
async def mark_hold_booked(payload: MarkBookedRequest) -> dict[str, Any]:
    """Internal endpoint for agent to mark slot hold as successfully converted."""
    telephony_manager.mark_hold_booked(payload.call_id, payload.hold_id)
    return {"status": "ok", "call_id": payload.call_id, "hold_id": payload.hold_id}


@router.get("/status")
async def telephony_status() -> dict[str, Any]:
    """Return live status of telephony manager, concurrency, and spend cap."""
    return {
        "active_calls_count": len(telephony_manager._active_sessions),
        "max_concurrent_calls": settings.max_concurrent_calls,
        "concurrency_limit_exceeded": telephony_manager.is_concurrency_limit_exceeded(),
        "today_spend_usd": telephony_manager.get_today_spend(),
        "daily_spend_cap_usd": settings.daily_spend_cap_usd,
        "spend_cap_exceeded": telephony_manager.is_spend_cap_exceeded(),
        "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        "livekit_sip_configured": bool(settings.livekit_sip_uri),
    }
