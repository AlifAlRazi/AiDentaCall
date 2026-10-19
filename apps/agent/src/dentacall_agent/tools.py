"""Tool dispatcher for executing voice receptionist tools against the Tool API."""

import logging
import uuid
from typing import Any

import httpx
from dentacall_api.main import create_app
from dentacall_api.tools.definitions import get_tool_definitions
from dentacall_core.settings import settings

logger = logging.getLogger(__name__)


class AgentToolDispatcher:
    """Executes agent tool calls by dispatching HTTP requests to the FastAPI Tool API."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        use_in_process_app: bool = True,
    ) -> None:
        """Initialize dispatcher with an existing client or create an in-process ASGI client."""
        self._owned_client = False
        if client:
            self.client = client
        elif use_in_process_app:
            # High-performance in-process client without requiring a running uvicorn port
            app = create_app()
            transport = httpx.ASGITransport(app=app)
            self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
            self._owned_client = True
        else:
            self.client = httpx.AsyncClient(base_url=settings.api_base_url)
            self._owned_client = True

    async def close(self) -> None:
        """Close the underlying HTTP client if owned by dispatcher."""
        if self._owned_client:
            await self.client.aclose()

    def get_definitions(self) -> list[dict[str, Any]]:
        """Return all 9 tool definitions in OpenAI/Claude JSON Schema format."""
        return get_tool_definitions()

    async def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        call_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch a tool execution by name and return the standard ToolResult envelope."""
        active_call_id = call_id or str(uuid.uuid4())
        headers = {
            "X-API-Key": settings.api_key,
            "X-Call-ID": active_call_id,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        logger.info(
            "[call_id=%s] Dispatching tool '%s' with args %s", active_call_id, name, arguments
        )

        endpoint_map = {
            "find_patient": ("/tools/find_patient", "POST"),
            "check_availability": ("/tools/check_availability", "POST"),
            "hold_slot": ("/tools/hold_slot", "POST"),
            "book_appointment": ("/tools/book_appointment", "POST"),
            "reschedule_appointment": ("/tools/reschedule_appointment", "POST"),
            "cancel_appointment": ("/tools/cancel_appointment", "POST"),
            "get_clinic_info": ("/tools/get_clinic_info", "GET"),
            "take_message": ("/tools/take_message", "POST"),
            "transfer_to_human": ("/tools/transfer_to_human", "POST"),
        }

        if name not in endpoint_map:
            return {
                "success": False,
                "data": None,
                "error_code": "UNKNOWN_TOOL",
                "error_message": f"Tool '{name}' is not recognized.",
                "hint": "Call only one of the 9 officially defined receptionist tools.",
            }

        path, method = endpoint_map[name]

        try:
            if method == "GET":
                response = await self.client.get(path, headers=headers)
            else:
                response = await self.client.post(path, json=arguments, headers=headers)

            try:
                result_json = response.json()
                if isinstance(result_json, dict):
                    return result_json
                return {
                    "success": False,
                    "data": None,
                    "error_code": "INVALID_RESPONSE_FORMAT",
                    "error_message": "Tool API returned a non-dictionary response.",
                    "hint": "Please try again or proceed with alternative options.",
                }
            except Exception:
                return {
                    "success": False,
                    "data": None,
                    "error_code": "JSON_PARSE_ERROR",
                    "error_message": f"Could not parse Tool API response (status {response.status_code}).",
                    "hint": "Please retry the operation.",
                }

        except Exception as exc:
            logger.exception("Error executing tool %s: %s", name, exc)
            return {
                "success": False,
                "data": None,
                "error_code": "TOOL_EXECUTION_ERROR",
                "error_message": str(exc),
                "hint": "The service encountered a temporary error. Try again shortly.",
            }
