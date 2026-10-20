"""Tests verifying scenario dataset integrity, schema conformity, and category coverage."""

from pathlib import Path

import yaml
from dentacall_evals.models import Scenario
from dentacall_evals.runner import EvalRunner

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "scenarios"


def test_scenario_count_meets_spec() -> None:
    """Ensure at least 50 distinct scenario files are present."""
    files = list(SCENARIOS_DIR.rglob("*.yaml")) + list(SCENARIOS_DIR.rglob("*.yml"))
    assert len(files) >= 50, f"Expected at least 50 scenarios, found {len(files)}"


def test_all_scenarios_conform_to_schema() -> None:
    """Validate each scenario against the Pydantic Scenario model."""
    files = sorted(list(SCENARIOS_DIR.rglob("*.yaml")) + list(SCENARIOS_DIR.rglob("*.yml")))
    assert len(files) >= 50

    scenario_ids: set[str] = set()

    for fpath in files:
        with open(fpath, encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)

        assert isinstance(raw_data, dict), f"File {fpath.name} is not a valid YAML mapping."
        scenario = Scenario.model_validate(raw_data)

        # Unique ID invariant
        assert scenario.id not in scenario_ids, f"Duplicate scenario ID found: {scenario.id}"
        scenario_ids.add(scenario.id)

        # Content validation
        assert scenario.name.strip(), f"Scenario {scenario.id} has empty name."
        assert scenario.category.strip(), f"Scenario {scenario.id} has empty category."
        assert scenario.description.strip(), f"Scenario {scenario.id} has empty description."
        assert scenario.caller.persona.strip(), f"Scenario {scenario.id} has empty persona."
        assert scenario.caller.goal.strip(), f"Scenario {scenario.id} has empty goal."
        assert len(scenario.caller.scripted_turns) > 0, (
            f"Scenario {scenario.id} has no scripted turns."
        )


def test_category_coverage() -> None:
    """Verify required categories from the specification are all represented."""
    runner = EvalRunner(scenarios_dir=SCENARIOS_DIR)
    scenarios = runner.load_scenarios()

    categories = {s.category for s in scenarios}
    required_categories = {
        "booking",
        "reschedule",
        "cancellation",
        "change_of_mind",
        "unclear_name",
        "fully_booked",
        "holiday",
        "emergency",
        "rude_caller",
        "medical_advice",
        "off_topic",
        "prompt_injection",
        "wrong_patient",
    }

    missing = required_categories - categories
    assert not missing, f"Missing required scenario categories: {missing}"
