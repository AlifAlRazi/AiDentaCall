"""Tests verifying OpenAPI schema generation and matching tool definitions."""

import pytest
from dentacall_api.tools.definitions import get_tool_definitions
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_openapi_docs_generated(client: AsyncClient) -> None:
    """Acceptance test: OpenAPI documentation is successfully generated and exposes all tools."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200

    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "DentaCall Tool API"
    assert schema["info"]["version"] == "0.1.0"

    paths = schema["paths"]

    # Verify all 9 required endpoints exist in the generated OpenAPI schema
    required_endpoints = [
        "/tools/find_patient",
        "/tools/check_availability",
        "/tools/hold_slot",
        "/tools/book_appointment",
        "/tools/reschedule_appointment",
        "/tools/cancel_appointment",
        "/tools/get_clinic_info",
        "/tools/take_message",
        "/tools/transfer_to_human",
    ]

    for endpoint in required_endpoints:
        assert endpoint in paths, f"Expected endpoint '{endpoint}' in OpenAPI schema"


def test_matching_tool_definitions_json_schema() -> None:
    """Verify tool definitions export includes all 9 tools matching JSON Schema specifications."""
    definitions = get_tool_definitions()
    assert len(definitions) == 9

    names = [d["name"] for d in definitions]
    expected_names = [
        "find_patient",
        "check_availability",
        "hold_slot",
        "book_appointment",
        "reschedule_appointment",
        "cancel_appointment",
        "get_clinic_info",
        "take_message",
        "transfer_to_human",
    ]

    for name in expected_names:
        assert name in names, f"Expected tool definition for '{name}'"

    for tool in definitions:
        assert "description" in tool
        assert "parameters" in tool
        assert "properties" in tool["parameters"]
