"""Integration tests for EvalRunner executing scenarios and generating reports."""

import json
from pathlib import Path

import pytest
from dentacall_agent.providers.base import LLMResponse
from dentacall_agent.providers.mock_provider import MockProvider
from dentacall_evals.runner import EvalRunner


@pytest.mark.asyncio
async def test_runner_executes_subset_and_saves_report(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    report_file = tmp_path / "benchmarks.md"

    # Mock provider simulating polite conversation
    mock_provider = MockProvider(
        canned_responses=[
            LLMResponse(
                content="Good day! Thank you for calling Grand Canal Dental Clinic. How can I help you?",
                prompt_tokens=10,
                completion_tokens=10,
            ),
            LLMResponse(
                content="I understand you are asking about December 26th. The clinic is closed for the Christmas bank holiday.",
                prompt_tokens=15,
                completion_tokens=15,
            ),
            LLMResponse(
                content="You are very welcome. Have a wonderful day, goodbye!",
                prompt_tokens=10,
                completion_tokens=10,
            ),
        ]
    )

    runner = EvalRunner(
        results_dir=results_dir,
        provider=mock_provider,
        use_llm_caller=False,
        use_llm_judge=False,
    )

    # Run on a targeted scenario
    summary = await runner.run_suite(scenario_id="holiday-003")

    assert summary.total_scenarios == 1
    assert summary.passed_scenarios == 1
    assert summary.safety_violation_count == 0
    assert summary.safety_pass_rate == 100.0

    # Verify JSON result persistence
    latest_json = results_dir / "latest.json"
    assert latest_json.exists()

    with open(latest_json, encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_scenarios"] == 1
    assert "category_breakdown" in data

    # Verify Markdown report writing
    runner.write_markdown_report(summary, report_file)
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "# DentaCall Voice Agent Benchmark Report" in content
    assert "Task Success Rate" in content
    assert "Executive Summary" in content
