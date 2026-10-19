"""Call ID context variable and logger filter for structured tracing."""

import contextvars
import logging

call_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("call_id", default="no-call-id")


class CallIDLogFilter(logging.Filter):
    """Logging filter that injects the current call_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.call_id = call_id_ctx.get()
        return True


def setup_api_logger(level: str = "INFO") -> logging.Logger:
    """Configure and return the root application logger with call_id formatting."""
    logger = logging.getLogger("dentacall_api")
    logger.setLevel(level)

    # Avoid adding duplicate handlers if already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [call_id=%(call_id)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(CallIDLogFilter())
        logger.addHandler(handler)

    return logger
