"""HTTP middleware for Call ID extraction and request performance logging."""

import time
import uuid

from dentacall_api.middleware.call_context import call_id_ctx, setup_api_logger
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = setup_api_logger()


class CallIDLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a Call ID to every request and logs execution times."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_call_id = request.headers.get("X-Call-ID")
        call_id = incoming_call_id or str(uuid.uuid4())
        token = call_id_ctx.set(call_id)
        from dentacall_core.json_logger import set_current_call_id

        set_current_call_id(call_id)

        start_time = time.perf_counter()
        logger.info("-> %s %s", request.method, request.url.path)

        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info(
                "<- %s %s [%d] (%.2fms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            response.headers["X-Call-ID"] = call_id
            return response
        except Exception:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception(
                "<- %s %s [FAILED] (%.2fms)", request.method, request.url.path, elapsed_ms
            )
            raise
        finally:
            call_id_ctx.reset(token)
