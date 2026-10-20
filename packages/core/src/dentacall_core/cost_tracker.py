"""Call cost calculation and financial tracking across voice, telephony, LLM, and TTS providers."""

from dataclasses import asdict, dataclass


@dataclass
class CallCostEstimate:
    """Detailed itemized cost breakdown for a voice/telephony call."""

    total_cost_usd: float
    twilio_cost_usd: float
    deepgram_cost_usd: float
    openai_cost_usd: float
    elevenlabs_cost_usd: float
    livekit_cost_usd: float
    duration_seconds: float
    prompt_tokens: int
    completion_tokens: int
    characters_synthesized: int

    def to_dict(self) -> dict[str, float | int]:
        """Convert cost estimate to dictionary representation."""
        return asdict(self)


class CallCostCalculator:
    """Calculates provider costs for voice agent calls based on actual usage metrics."""

    # Provider unit pricing (USD)
    # Twilio Programmable Voice: $0.014/minute
    TWILIO_COST_PER_SECOND: float = 0.014 / 60.0
    # Deepgram Nova-3 Streaming: $0.0043/minute
    DEEPGRAM_COST_PER_SECOND: float = 0.0043 / 60.0
    # OpenAI gpt-4o-mini: $0.15 per 1M input tokens, $0.60 per 1M output tokens
    OPENAI_PROMPT_TOKEN_COST: float = 0.15 / 1_000_000.0
    OPENAI_COMPLETION_TOKEN_COST: float = 0.60 / 1_000_000.0
    # ElevenLabs Turbo v2.5: $25.00 per 1M characters (~$0.000025/char)
    ELEVENLABS_COST_PER_CHAR: float = 25.0 / 1_000_000.0
    # LiveKit Cloud RTC Audio: $0.004/minute per participant
    LIVEKIT_COST_PER_SECOND: float = 0.004 / 60.0

    @classmethod
    def calculate(
        cls,
        duration_seconds: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        characters_synthesized: int = 0,
        is_telephony: bool = True,
    ) -> CallCostEstimate:
        """Calculate total and itemized costs for a completed call."""
        sec = max(0.0, duration_seconds)

        twilio_cost = sec * cls.TWILIO_COST_PER_SECOND if is_telephony else 0.0
        deepgram_cost = sec * cls.DEEPGRAM_COST_PER_SECOND
        openai_cost = (
            prompt_tokens * cls.OPENAI_PROMPT_TOKEN_COST
            + completion_tokens * cls.OPENAI_COMPLETION_TOKEN_COST
        )
        elevenlabs_cost = characters_synthesized * cls.ELEVENLABS_COST_PER_CHAR
        livekit_cost = sec * cls.LIVEKIT_COST_PER_SECOND

        total = twilio_cost + deepgram_cost + openai_cost + elevenlabs_cost + livekit_cost

        return CallCostEstimate(
            total_cost_usd=round(total, 6),
            twilio_cost_usd=round(twilio_cost, 6),
            deepgram_cost_usd=round(deepgram_cost, 6),
            openai_cost_usd=round(openai_cost, 6),
            elevenlabs_cost_usd=round(elevenlabs_cost, 6),
            livekit_cost_usd=round(livekit_cost, 6),
            duration_seconds=round(sec, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            characters_synthesized=characters_synthesized,
        )
