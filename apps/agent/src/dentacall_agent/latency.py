"""Latency metrics and audio pipeline telemetry for DentaCall LiveKit agent."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TurnLatencyRecord:
    """Latency metrics for a single conversational audio turn."""

    turn_id: str
    timestamp_utc: datetime = field(default_factory=lambda: datetime.now(UTC))
    stt_duration_ms: float = 0.0
    llm_ttft_ms: float = 0.0  # Time to first token
    tool_duration_ms: float = 0.0
    tts_ttfb_ms: float = 0.0  # Time to first audio byte
    total_ttfa_ms: float = 0.0  # End-to-end Time to First Audio
    characters_synthesized: int = 0
    deepgram_request_id: str | None = None
    target_met: bool = False  # True if TTFA <= 1200ms (1.2s target)

    def compute_summary(self) -> dict[str, Any]:
        self.target_met = self.total_ttfa_ms <= 1200.0
        return {
            "turn_id": self.turn_id,
            "stt_ms": round(self.stt_duration_ms, 1),
            "llm_ttft_ms": round(self.llm_ttft_ms, 1),
            "tool_ms": round(self.tool_duration_ms, 1),
            "tts_ttfb_ms": round(self.tts_ttfb_ms, 1),
            "total_ttfa_ms": round(self.total_ttfa_ms, 1),
            "characters": self.characters_synthesized,
            "deepgram_request_id": self.deepgram_request_id,
            "target_met": self.target_met,
        }


class LatencyTracker:
    """Collects and aggregates real-time latency across audio conversation sessions."""

    def __init__(self) -> None:
        self.turns: list[TurnLatencyRecord] = []
        self.total_characters_sent: int = 0

    def record_turn(self, record: TurnLatencyRecord) -> None:
        record.target_met = record.total_ttfa_ms <= 1200.0
        self.turns.append(record)
        self.total_characters_sent += record.characters_synthesized
        logger.info(
            "Turn latency recorded: TTFA=%.1fms (STT=%.1fms, LLM=%.1fms, Tool=%.1fms, TTS=%.1fms, chars=%d, target_met=%s)",
            record.total_ttfa_ms,
            record.stt_duration_ms,
            record.llm_ttft_ms,
            record.tool_duration_ms,
            record.tts_ttfb_ms,
            record.characters_synthesized,
            record.target_met,
        )

    def get_aggregate_stats(self) -> dict[str, Any]:
        if not self.turns:
            return {
                "turn_count": 0,
                "avg_stt_ms": 0.0,
                "avg_llm_ttft_ms": 0.0,
                "avg_tool_ms": 0.0,
                "avg_tts_ttfb_ms": 0.0,
                "avg_total_ttfa_ms": 0.0,
                "p95_total_ttfa_ms": 0.0,
                "target_success_rate": 100.0,
                "total_characters_sent": 0,
            }

        total_turns = len(self.turns)
        avg_stt = sum(t.stt_duration_ms for t in self.turns) / total_turns
        avg_llm = sum(t.llm_ttft_ms for t in self.turns) / total_turns
        avg_tool = sum(t.tool_duration_ms for t in self.turns) / total_turns
        avg_tts = sum(t.tts_ttfb_ms for t in self.turns) / total_turns
        avg_ttfa = sum(t.total_ttfa_ms for t in self.turns) / total_turns

        sorted_ttfa = sorted(t.total_ttfa_ms for t in self.turns)
        p95_idx = int(0.95 * total_turns)
        p95_ttfa = sorted_ttfa[min(p95_idx, total_turns - 1)]

        met_count = sum(1 for t in self.turns if t.target_met)
        success_rate = (met_count / total_turns) * 100.0

        return {
            "turn_count": total_turns,
            "avg_stt_ms": round(avg_stt, 1),
            "avg_llm_ttft_ms": round(avg_llm, 1),
            "avg_tool_ms": round(avg_tool, 1),
            "avg_tts_ttfb_ms": round(avg_tts, 1),
            "avg_total_ttfa_ms": round(avg_ttfa, 1),
            "p95_total_ttfa_ms": round(p95_ttfa, 1),
            "target_success_rate": round(success_rate, 1),
            "total_characters_sent": self.total_characters_sent,
        }
