"""Global exception handlers ensuring clean error responses and zero stack trace leakage."""

import logging

from dentacall_core.booking import BookingError
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("dentacall_api")


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers on the FastAPI application."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Translate Pydantic validation errors into clean, LLM-readable error hints."""
        errors: list[str] = []
        for err in exc.errors():
            loc = " -> ".join(str(item) for item in err.get("loc", []))
            msg = err.get("msg", "invalid value")
            errors.append(f"{loc}: {msg}")

        combined_msg = "; ".join(errors)
        logger.warning("Request validation failed on %s: %s", request.url.path, combined_msg)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "data": None,
                "error_code": "INVALID_ARGUMENTS",
                "error_message": combined_msg,
                "hint": "Review the field requirements and provide valid arguments formatted according to the tool schema.",
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Ensure standard HTTP exceptions follow the ToolResult payload structure."""
        if isinstance(exc.detail, dict) and "error_code" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "data": None,
                "error_code": f"HTTP_{exc.status_code}",
                "error_message": str(exc.detail),
                "hint": "Check the endpoint parameters and authorization headers.",
            },
        )

    @app.exception_handler(BookingError)
    async def booking_error_handler(request: Request, exc: BookingError) -> JSONResponse:
        """Handle domain booking errors cleanly."""
        logger.warning("Domain booking error on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "success": False,
                "data": None,
                "error_code": "BOOKING_CONFLICT",
                "error_message": str(exc),
                "hint": "Check slot availability and ensure the appointment status allows this action.",
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unhandled exceptions to guarantee zero stack trace leakage."""
        logger.exception("Unhandled server exception on %s: %s", request.url.path, exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "data": None,
                "error_code": "INTERNAL_SERVER_ERROR",
                "error_message": "An internal server error occurred while processing the request.",
                "hint": "The service encountered an unexpected condition. Please retry or escalate to reception.",
            },
        )
