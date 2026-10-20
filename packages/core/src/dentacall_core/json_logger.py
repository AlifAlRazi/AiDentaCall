"""Structured JSON logger with call ID context and OpenTelemetry trace correlation."""

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from opentelemetry import trace

# Context variable to hold active call_id for the current task/coroutine
current_call_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_call_id", default=None
)


def set_current_call_id(call_id: str | None) -> None:
    """Set the active call_id in the current contextvar."""
    current_call_id.set(call_id)


def get_current_call_id() -> str | None:
    """Retrieve the active call_id from contextvar."""
    return current_call_id.get()


class JSONLogFormatter(logging.Formatter):
    """Custom logging formatter that outputs one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        # Determine call_id from record attribute or contextvar
        call_id = getattr(record, "call_id", None) or get_current_call_id()

        # Extract active OpenTelemetry span context if present
        span = trace.get_current_span()
        span_context = span.get_span_context() if span else None
        trace_id = (
            format(span_context.trace_id, "032x")
            if span_context and span_context.is_valid
            else None
        )
        span_id = (
            format(span_context.span_id, "016x") if span_context and span_context.is_valid else None
        )

        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "call_id": call_id,
        }

        if trace_id:
            log_data["trace_id"] = trace_id
            log_data["span_id"] = span_id

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include custom extra fields if attached to record
        for key, val in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "call_id",
            }:
                try:
                    json.dumps(val)
                    log_data[key] = val
                except (TypeError, OverflowError):
                    log_data[key] = str(val)

        return json.dumps(log_data)


def setup_structured_logging(
    level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Configure root logger to output structured JSON or standard format."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to prevent duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if log_format.lower() == "json":
        handler.setFormatter(JSONLogFormatter())
    else:
        standard_formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(name)s [%(filename)s:%(lineno)d] (call_id: %(call_id)s): %(message)s"
        )
        handler.setFormatter(standard_formatter)

    root_logger.addHandler(handler)
