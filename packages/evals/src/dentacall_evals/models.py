"""Data models and schemas for DentaCall evaluation harness."""

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class ScenarioCaller(BaseModel):
    """Specification of the caller persona and script."""

    name: str = "Test Caller"
    phone: str | None = None
    dob: str | None = None
    persona: str = "A standard patient calling the dental clinic."
    goal: str = "Achieve their clinical or administrative goal."
    scripted_turns: list[str] = Field(default_factory=list)


class ScenarioExpected(BaseModel):
    """Expected criteria and invariants for scoring."""

    task_success: bool = True
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    required_keywords: list[str] = Field(default_factory=list)
    forbidden_keywords: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    max_turns: int = 10
    emergency_escalation: bool = False


class Scenario(BaseModel):
    """A benchmark evaluation scenario."""

    id: str
    name: str
    category: str
    description: str
    caller: ScenarioCaller = Field(default_factory=ScenarioCaller)
    expected: ScenarioExpected = Field(default_factory=ScenarioExpected)


@dataclass
class TurnRecord:
    """Record of a single conversational turn."""

    turn_idx: int
    speaker: str  # "caller" or "agent"
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class MetricScores:
    """Fine-grained metric scores for an evaluation run."""

    task_success: bool
    tools_score: float  # 0.0 to 1.0
    safety_score: float  # 1.0 = 0 safety violations, 0.0 = violations present
    safety_violations: list[str] = field(default_factory=list)
    confirmation_score: float = 1.0  # 1.0 = confirmed before write, 0.0 = unconfirmed write
    tone_score: float = 5.0  # 1.0 to 5.0
    clarity_score: float = 5.0  # 1.0 to 5.0
    judge_rubric_explanation: str = ""
    turn_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ScenarioResult:
    """Result of evaluating a single scenario."""

    scenario_id: str
    category: str
    name: str
    passed: bool
    metrics: MetricScores
    turns: list[TurnRecord] = field(default_factory=list)
    error: str | None = None


@dataclass
class EvalRunSummary:
    """Aggregated summary of a complete benchmark evaluation suite run."""

    run_id: str
    timestamp_utc: str
    model: str
    total_scenarios: int
    passed_scenarios: int
    task_success_rate: float
    safety_pass_rate: float
    safety_violation_count: int
    avg_turns: float
    avg_token_cost_usd: float
    avg_tone_score: float
    avg_clarity_score: float
    category_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    results: list[ScenarioResult] = field(default_factory=list)
