"""API Key authentication dependency for secure agent-to-API communication."""

from dentacall_core.settings import settings
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Verify that the caller provided the valid X-API-Key header."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "data": None,
                "error_code": "UNAUTHORIZED",
                "error_message": "Missing 'X-API-Key' authentication header.",
                "hint": "Include 'X-API-Key: <your-key>' in the HTTP headers.",
            },
        )

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "data": None,
                "error_code": "INVALID_API_KEY",
                "error_message": "The provided 'X-API-Key' is invalid.",
                "hint": "Check your API key configuration in .env.",
            },
        )

    return api_key
