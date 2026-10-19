"""In-memory sliding window rate limiter middleware."""

import time
from typing import ClassVar

from dentacall_core.settings import settings
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding window rate limiter per client IP address."""

    # Dictionary mapping client_ip -> list of epoch timestamps
    _request_history: ClassVar[dict[str, list[float]]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting on docs, openapi, and health checks
        path = request.url.path
        if path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60.0  # 1 minute window

        history = self._request_history.get(client_ip, [])
        # Prune timestamps older than 60 seconds
        recent = [ts for ts in history if ts > window_start]

        if len(recent) >= settings.rate_limit_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "data": None,
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "error_message": f"Rate limit of {settings.rate_limit_per_minute} requests/minute exceeded.",
                    "hint": "Please wait a moment before sending additional requests.",
                },
                headers={"Retry-After": "5"},
            )

        recent.append(now)
        self._request_history[client_ip] = recent

        return await call_next(request)
