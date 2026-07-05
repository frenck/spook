"""Tests for the Spook chance condition."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.condition import ConditionConfig
import voluptuous as vol

from custom_components.spook.condition import async_get_conditions
from custom_components.spook.ectoplasms.spook.conditions.chance import SpookCondition
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def test_condition_is_discovered(hass: HomeAssistant) -> None:
    """Test the chance condition is discovered as spook.chance."""
    conditions = await async_get_conditions(hass)
    assert conditions["chance"] is SpookCondition


async def test_discovery_result_is_cached(hass: HomeAssistant) -> None:
    """Test repeated discovery returns the cached mapping."""
    first = await async_get_conditions(hass)
    second = await async_get_conditions(hass)
    assert first is second


async def test_config_validation(hass: HomeAssistant) -> None:
    """Test the condition validates its percentage option."""
    percentage = 20
    valid = await SpookCondition.async_validate_config(
        hass, {"options": {"percentage": percentage}}
    )
    assert valid["options"]["percentage"] == percentage

    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(
            hass, {"options": {"percentage": 200}}
        )
    with pytest.raises(vol.Invalid):
        await SpookCondition.async_validate_config(hass, {"options": {}})


async def test_full_chance_always_passes(hass: HomeAssistant) -> None:
    """Test 100 percent always passes."""
    condition = SpookCondition(hass, ConditionConfig(options={"percentage": 100}))
    assert all(condition(hass) for _ in range(50))


async def test_zero_chance_never_passes(hass: HomeAssistant) -> None:
    """Test 0 percent never passes."""
    condition = SpookCondition(hass, ConditionConfig(options={"percentage": 0}))
    assert not any(condition(hass) for _ in range(50))
