"""Tests for the Spook cooldown condition."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.condition import ConditionConfig
from homeassistant.util import dt as dt_util
import voluptuous as vol

from custom_components.spook.condition import async_get_conditions
from custom_components.spook.ectoplasms.spook.conditions.cooldown import SpookCondition
import pytest

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant

_DURATION = timedelta(minutes=5)


def _condition(hass: HomeAssistant) -> SpookCondition:
    """Build a cooldown condition with a five minute duration."""
    return SpookCondition(hass, ConditionConfig(options={"duration": _DURATION}))


def _variables(last_triggered: datetime | str | None) -> dict:
    """Build the automation `this` variables with a last-triggered time."""
    return {"this": {"attributes": {"last_triggered": last_triggered}}}


async def test_condition_is_discovered(hass: HomeAssistant) -> None:
    """Test the cooldown condition is discovered as spook.cooldown."""
    conditions = await async_get_conditions(hass)
    assert conditions["cooldown"] is SpookCondition


async def test_config_validation(hass: HomeAssistant) -> None:
    """Test the condition validates its duration option."""
    valid = await SpookCondition.async_validate_config(
        hass, {"options": {"duration": "00:05:00"}}
    )
    assert valid["options"]["duration"] == _DURATION

    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(hass, {"options": {}})


async def test_recent_run_blocks(hass: HomeAssistant) -> None:
    """Test a run within the cooldown fails the condition."""
    recent = dt_util.utcnow() - timedelta(minutes=1)
    assert _condition(hass)(hass, _variables(recent)) is False


async def test_elapsed_run_passes(hass: HomeAssistant) -> None:
    """Test a run older than the cooldown passes the condition."""
    old = dt_util.utcnow() - timedelta(minutes=10)
    assert _condition(hass)(hass, _variables(old)) is True


async def test_string_last_triggered_is_parsed(hass: HomeAssistant) -> None:
    """Test a restored ISO-string last-triggered is handled."""
    old = (dt_util.utcnow() - timedelta(minutes=10)).isoformat()
    assert _condition(hass)(hass, _variables(old)) is True


async def test_never_run_passes(hass: HomeAssistant) -> None:
    """Test the condition passes when there is no last-run info."""
    assert _condition(hass)(hass, _variables(None)) is True
    assert _condition(hass)(hass, {}) is True
    assert _condition(hass)(hass, None) is True
