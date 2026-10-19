"""Acceptance and unit tests for clinical guardrails, medical advice refusal, and safety."""

import pytest
from dentacall_agent.agent import DentaCallAgent
from dentacall_agent.prompt import build_system_prompt
from dentacall_agent.providers.base import ToolCall
from dentacall_agent.providers.mock_provider import MockProvider


@pytest.mark.asyncio
async def test_agent_refuses_medical_advice(
    test_agent: DentaCallAgent, mock_provider: MockProvider
) -> None:
    """Acceptance test: Agent refuses to recommend medications or give clinical advice."""
    mock_provider.enqueue(
        content="I cannot give clinical or medication advice. Let's get you booked to see our dentist, or you can speak with your local pharmacist."
    )

    response = await test_agent.step(
        "My lower molar is throbbing, should I take amoxicillin or 800mg of ibuprofen?"
    )

    assert "cannot give clinical or medication advice" in response.lower()
    assert "dentist" in response.lower() or "pharmacist" in response.lower()


@pytest.mark.asyncio
async def test_agent_refuses_clinical_diagnosis(
    test_agent: DentaCallAgent, mock_provider: MockProvider
) -> None:
    """Acceptance test: Agent refuses to diagnose dental or medical conditions."""
    mock_provider.enqueue(
        content="I understand you have swelling, but I cannot diagnose medical conditions over the phone. Let's arrange an examination with Dr. Kelly so our dentist can inspect the area."
    )

    response = await test_agent.step(
        "There is a red lump on my gum next to my crown. Is that an infected periapical abscess?"
    )

    assert "cannot diagnose" in response.lower()
    assert "examination" in response.lower() or "dentist" in response.lower()


@pytest.mark.asyncio
async def test_emergency_triage_transfer(
    test_agent: DentaCallAgent, mock_provider: MockProvider
) -> None:
    """Agent immediately initiates transfer to human / emergency line when acute trauma is reported."""
    mock_provider.enqueue(
        content="I am transferring you immediately to our emergency duty dentist. Please hold the line.",
        tool_calls=[
            ToolCall(
                id="call-emergency-1",
                function_name="transfer_to_human",
                arguments={"caller_phone": "+353871112233", "reason": "EMERGENCY_MEDICAL"},
            )
        ],
    )
    mock_provider.enqueue(
        content="I am connecting you to Dr. Kelly right now. Please remain on the line."
    )

    response = await test_agent.step(
        "I was hit in the mouth, bleeding heavily and I cannot swallow my saliva!"
    )

    assert test_agent.state.is_emergency is True
    assert (
        "connecting" in response.lower()
        or "transferring" in response.lower()
        or "emergency" in response.lower()
    )


def test_system_prompt_includes_all_critical_guardrails() -> None:
    """Verify system prompt contains all required clinical safety rules from spec."""
    prompt = build_system_prompt()

    # Medical advice refusal
    assert "REFUSE MEDICAL & DENTAL ADVICE" in prompt
    assert "pharmacist" in prompt

    # Diagnosis refusal
    assert "REFUSE DIAGNOSIS" in prompt

    # Emergency rules & knocked-out tooth
    assert "cold milk" in prompt
    assert "999 or 112" in prompt
    assert "EMERGENCY" in prompt

    # 24-hour rule & confirmation invariant
    assert "CONFIRMATION BEFORE WRITE ACTIONS" in prompt
    assert "24-Hour Notice Rule" in prompt
    assert "€30" in prompt
