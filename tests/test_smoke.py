"""Smoke test for DentaCall monorepo setup and core package imports."""

import pytest
from dentacall_core import ClinicConfig, __version__


@pytest.mark.smoke
def test_smoke_core_import_and_config() -> None:
    """Verify core package import, version, and basic typed configuration."""
    assert __version__ == "0.1.0"
    config = ClinicConfig()
    assert config.timezone == "Europe/Dublin"
    assert config.cancellation_notice_hours == 24
    assert config.name == "Grand Canal Dental Clinic"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_async_execution() -> None:
    """Verify that asyncio test runner is operating correctly."""
    result = await _async_add(21, 21)
    assert result == 42


async def _async_add(a: int, b: int) -> int:
    return a + b
