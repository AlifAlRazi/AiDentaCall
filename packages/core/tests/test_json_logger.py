"""Tests for structured JSON logging with call ID context and trace correlation."""

import json
import logging

from dentacall_core.json_logger import (
    JSONLogFormatter,
    set_current_call_id,
)
from dentacall_core.tracing import trace_turn


def test_json_log_formatter_includes_call_id() -> None:
    """Verify that JSONLogFormatter injects call_id from contextvar into json output."""
    formatter = JSONLogFormatter()
    logger = logging.getLogger("test_logger_call_id")

    set_current_call_id("call-uuid-999")
    record = logger.makeRecord(
        name="test_logger",
        level=logging.INFO,
        fn="test_file.py",
        lno=42,
        msg="Slot hold created successfully",
        args=(),
        exc_info=None,
    )

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["level"] == "INFO"
    assert data["message"] == "Slot hold created successfully"
    assert data["call_id"] == "call-uuid-999"
    assert "timestamp" in data


def test_json_log_formatter_correlates_active_trace() -> None:
    """Verify that when an OpenTelemetry span is active, trace_id and span_id are included in the JSON log."""
    formatter = JSONLogFormatter()
    logger = logging.getLogger("test_logger_trace")

    with trace_turn(call_id="call-trace-1", turn_id="turn-1", turn_number=1):
        record = logger.makeRecord(
            name="test_logger",
            level=logging.INFO,
            fn="test_file.py",
            lno=10,
            msg="Executing LLM inference",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert "trace_id" in data
        assert "span_id" in data
        assert len(data["trace_id"]) == 32
        assert len(data["span_id"]) == 16
