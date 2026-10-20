"""LiveKit Voice Agent Worker for DentaCall clinical dental reception."""

import asyncio
import logging
import uuid
from typing import Any

from dentacall_core.settings import settings
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
)
from livekit.agents.voice import Agent, AgentSession
from livekit.agents.voice.agent_session import TurnHandlingOptions
from livekit.agents.voice.turn import EndpointingOptions, InterruptionOptions
from livekit.plugins import deepgram, elevenlabs, openai, silero

from dentacall_agent.latency import LatencyTracker, TurnLatencyRecord
from dentacall_agent.livekit_tools import create_livekit_tools
from dentacall_agent.tools import AgentToolDispatcher
from dentacall_agent.voice_prompt import build_voice_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dentacall.voice_worker")

# Global latency tracker for real-time observability
latency_tracker = LatencyTracker()


async def entrypoint(ctx: JobContext) -> None:
    """LiveKit agent worker entrypoint called when a room session connects."""
    call_id = str(uuid.uuid4())
    logger.info(
        "Initializing LiveKit Voice Agent session for call_id=%s, room=%s", call_id, ctx.room.name
    )

    # 1. Connect audio-only to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # 2. Wait for participant to join
    participant = await ctx.wait_for_participant()
    logger.info(
        "Participant joined: identity=%s, name=%s (call_id=%s)",
        participant.identity,
        participant.name,
        call_id,
    )

    # Telephony caller ID detection
    from dentacall_core.telephony import telephony_manager

    caller_phone: str | None = None
    identity = participant.identity or ""
    # Check SIP identity format: sip:+353... or raw +353...
    if "+" in identity:
        caller_phone = identity[identity.find("+") :]
    elif participant.attributes and "sip.phoneNumber" in participant.attributes:
        caller_phone = participant.attributes["sip.phoneNumber"]

    telephony_session = telephony_manager.start_call_session(
        call_id=call_id,
        caller_phone=caller_phone,
    )

    # Register disconnect hook to release holds and clean up on drop
    async def cleanup_telephony_session() -> None:
        await telephony_manager.handle_call_disconnect(call_id=call_id, reason="DISCONNECTED")

    ctx.add_shutdown_callback(lambda: asyncio.create_task(cleanup_telephony_session()))

    # 3. Setup dispatcher and tools
    dispatcher = AgentToolDispatcher()
    tools = create_livekit_tools(dispatcher, call_id=call_id)

    # Pre-fetch patient if caller phone is identified
    patient_first_name: str | None = None
    if caller_phone:
        try:
            patient_res = await dispatcher.execute_tool(
                "find_patient", {"phone": caller_phone}, call_id=call_id
            )
            if patient_res.get("success") and patient_res.get("data", {}).get("patients"):
                patient = patient_res["data"]["patients"][0]
                patient_first_name = patient.get("first_name")
                telephony_session.patient_id = patient.get("id")
                telephony_session.patient_name = (
                    f"{patient.get('first_name')} {patient.get('last_name')}"
                )
                logger.info(
                    "[call_id=%s] Recognized patient: %s (%s)",
                    call_id,
                    telephony_session.patient_name,
                    caller_phone,
                )
        except Exception as e:
            logger.warning("[call_id=%s] Error during patient pre-fetch: %s", call_id, e)

    # 4. Initialize Streaming STT (Deepgram Nova-3)
    # Per requirements: Nova-3, English, punctuate, interim results, log request ID
    stt = deepgram.STT(
        model="nova-3",
        language="en",
        punctuate=True,
        interim_results=True,
        api_key=settings.deepgram_api_key,
    )

    # 5. Initialize VAD (Silero)
    vad = silero.VAD.load()

    # 6. Initialize LLM (OpenAI gpt-4o-mini)
    llm = openai.LLM(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )

    # 7. Initialize Streaming TTS (ElevenLabs Turbo v2.5)
    # Per requirements: fast streaming model, track character count, handle quota
    tts = elevenlabs.TTS(
        model=settings.elevenlabs_model,
        api_key=settings.elevenlabs_api_key,
        voice_id=settings.elevenlabs_voice_id,
    )

    # 8. Configure turn handling, VAD endpointing, and barge-in
    turn_handling = TurnHandlingOptions(
        interruption=InterruptionOptions(
            enabled=True,
            mode="vad",
            min_duration=0.3,
            min_words=1,
        ),
        endpointing=EndpointingOptions(
            mode="dynamic",
            min_delay=0.4,
            max_delay=1.2,
        ),
    )

    # 9. Build Voice Agent
    agent = Agent(
        instructions=build_voice_prompt(),
        tools=tools,
        stt=stt,
        vad=vad,
        llm=llm,
        tts=tts,
        turn_handling=turn_handling,
    )

    session = AgentSession(
        stt=stt,
        vad=vad,
        llm=llm,
        tts=tts,
        tools=tools,
        turn_handling=turn_handling,
    )

    # 10. Observability & Event Listeners
    current_turn = TurnLatencyRecord(turn_id=str(uuid.uuid4()))
    turn_start_time = asyncio.get_event_loop().time()

    @session.on("user_started_speaking")
    def on_user_started_speaking(*args: Any, **kwargs: Any) -> None:
        nonlocal turn_start_time, current_turn
        turn_start_time = asyncio.get_event_loop().time()
        current_turn = TurnLatencyRecord(turn_id=str(uuid.uuid4()))
        logger.info("[call_id=%s] Caller started speaking (barge-in active)", call_id)

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: Any = None, *args: Any, **kwargs: Any) -> None:
        now = asyncio.get_event_loop().time()
        current_turn.stt_duration_ms = (now - turn_start_time) * 1000.0
        # Log Deepgram request id if present in event/metadata
        if hasattr(ev, "request_id") and ev.request_id:
            current_turn.deepgram_request_id = ev.request_id
            logger.info("[call_id=%s] Deepgram STT request_id: %s", call_id, ev.request_id)
        logger.info(
            "[call_id=%s] User input transcribed in %.1fms: %s",
            call_id,
            current_turn.stt_duration_ms,
            getattr(ev, "transcript", ""),
        )

    @session.on("speech_created")
    def on_speech_created(ev: Any = None, *args: Any, **kwargs: Any) -> None:
        now = asyncio.get_event_loop().time()
        current_turn.total_ttfa_ms = (now - turn_start_time) * 1000.0
        text = getattr(ev, "text", "") or ""
        current_turn.characters_synthesized += len(text)
        logger.info(
            "[call_id=%s] Agent started speaking (TTFA=%.1fms, chars=%d)",
            call_id,
            current_turn.total_ttfa_ms,
            len(text),
        )
        latency_tracker.record_turn(current_turn)

    @session.on("error")
    def on_session_error(ev: Any = None, *args: Any, **kwargs: Any) -> None:
        error_msg = str(getattr(ev, "error", ev))
        logger.error("[call_id=%s] Session error encountered: %s", call_id, error_msg)
        if "quota" in error_msg.lower() or "credits" in error_msg.lower():
            logger.critical(
                "[call_id=%s] ElevenLabs TTS credits exhausted. Stopping voice generation to prevent retry loop.",
                call_id,
            )

    # 11. Start agent session on the room
    logger.info("[call_id=%s] Starting AgentSession in room %s...", call_id, ctx.room.name)
    await session.start(room=ctx.room, agent=agent)

    # 12. Speak initial warm greeting with AI and recording disclosure
    if patient_first_name:
        greeting = (
            f"Hello {patient_first_name}, thank you for calling Grand Canal Dental Clinic. "
            "Please note that this call is handled by an AI assistant and may be recorded "
            "for quality and training purposes. How can I help you today?"
        )
    else:
        greeting = (
            "Thank you for calling Grand Canal Dental Clinic. "
            "Please note that this call is handled by an AI assistant and may be recorded "
            "for quality and training purposes. How can I help you today?"
        )
    current_turn.characters_synthesized += len(greeting)
    await session.say(greeting, allow_interruptions=True)
    logger.info("[call_id=%s] Agent greeting spoken. Waiting for caller inquiry...", call_id)


def main() -> None:
    """CLI entrypoint for running the LiveKit voice agent worker."""
    options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="dentacall-voice-agent",
        ws_url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )
    cli.run_app(options)


if __name__ == "__main__":
    main()
