"""Unit tests for LLMJudge rubric and heuristic evaluator."""

import pytest
from dentacall_evals.judge import LLMJudge
from dentacall_evals.models import Scenario, ScenarioCaller, ScenarioExpected, TurnRecord


@pytest.mark.asyncio
async def test_judge_heuristic_clean_conversation() -> None:
    judge = LLMJudge(provider=None)
    scenario = Scenario(
        id="test-judge-01",
        name="Test Clean Interaction",
        category="booking",
        description="Testing tone evaluation",
        caller=ScenarioCaller(),
        expected=ScenarioExpected(),
    )

    turns = [
        TurnRecord(turn_idx=1, speaker="caller", text="Hello, I want to book a checkup."),
        TurnRecord(
            turn_idx=2,
            speaker="agent",
            text="Good day! I would be delighted to help you. Tuesday at 10:00 AM is available.",
        ),
        TurnRecord(turn_idx=3, speaker="caller", text="Yes please."),
        TurnRecord(
            turn_idx=4, speaker="agent", text="Thank you, you are booked. Have a wonderful day."
        ),
    ]

    tone, clarity, explanation = await judge.evaluate(scenario, turns)
    assert tone >= 4.5
    assert clarity >= 4.5
    assert "receptionist tone" in explanation


@pytest.mark.asyncio
async def test_judge_heuristic_detects_markdown_formatting() -> None:
    judge = LLMJudge(provider=None)
    scenario = Scenario(
        id="test-judge-02",
        name="Test Markdown Presence",
        category="booking",
        description="Testing markdown penalty",
        caller=ScenarioCaller(),
        expected=ScenarioExpected(),
    )

    turns = [
        TurnRecord(turn_idx=1, speaker="caller", text="What are your services?"),
        TurnRecord(
            turn_idx=2,
            speaker="agent",
            text="### Services:\n - Routine Exam: €65\n - Hygiene Clean: €85\n - Root Canal: €550",
        ),
    ]

    tone, clarity, explanation = await judge.evaluate(scenario, turns)
    assert clarity < 4.5
    assert "markdown formatting" in explanation.lower()
