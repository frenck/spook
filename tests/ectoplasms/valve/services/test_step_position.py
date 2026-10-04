"""Tests for the valve increase and decrease position actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.exceptions import ServiceNotSupported
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
import pytest

from custom_components.spook.ectoplasms.valve.services.decrease_position import (
    SpookService as DecreaseService,
)
from custom_components.spook.ectoplasms.valve.services.increase_position import (
    SpookService as IncreaseService,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )


class FakeValve(ValveEntity):
    """A valve that remembers where it was told to go."""

    _attr_should_poll = False
    _attr_reports_position = True
    _attr_supported_features = (
        ValveEntityFeature.OPEN
        | ValveEntityFeature.CLOSE
        | ValveEntityFeature.SET_POSITION
    )

    def __init__(self, name: str, position: int | None) -> None:
        """Initialize the valve."""
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_current_valve_position = position
        self.told: list[int] = []

    async def async_set_valve_position(self, position: int) -> None:
        """Go to the new position."""
        self.told.append(position)
        self._attr_current_valve_position = position
        self.async_write_ha_state()


class FakeShutoffValve(FakeValve):
    """A shutoff valve that only knows open and closed."""

    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE


async def _setup(
    hass: HomeAssistant, *valves: ValveEntity, parallel_updates: int = 0
) -> None:
    """Set up these valves and both actions."""
    assert await async_setup_component(hass, "homeassistant", {})

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.VALVE])
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add(list(valves))

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    platform = MockPlatform(async_setup_entry=_setup_platform)
    if parallel_updates:
        platform.PARALLEL_UPDATES = parallel_updates  # type: ignore[attr-defined]
    mock_platform(hass, "fake.valve", platform)

    class _Flow(ConfigFlow, domain="fake"):
        """A config flow that does nothing."""

    with mock_config_flow("fake", _Flow):
        entry = MockConfigEntry(domain="fake")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    IncreaseService(hass).async_register()
    DecreaseService(hass).async_register()
    await hass.async_block_till_done()


async def _step(hass: HomeAssistant, service: str, entity_id: str, **data: Any) -> None:
    """Step a valve."""
    await hass.services.async_call(
        "valve", service, {"entity_id": entity_id, **data}, blocking=True
    )


async def test_ten_percent_unless_told_otherwise(hass: HomeAssistant) -> None:
    """Test the default step, and a given one."""
    valve = FakeValve("valve", 50)
    await _setup(hass, valve)

    await _step(hass, "increase_position", "valve.valve")
    await _step(hass, "decrease_position", "valve.valve", step=25)

    assert valve.told == [60, 35]


async def test_open_and_closed_are_the_limits(hass: HomeAssistant) -> None:
    """Test a step stops at fully open or closed, and one there does nothing."""
    almost = FakeValve("almost", 95)
    shut = FakeValve("shut", 0)
    await _setup(hass, almost, shut)

    await _step(hass, "increase_position", "valve.almost")
    await _step(hass, "decrease_position", "valve.shut")

    assert almost.told == [100]
    assert not shut.told


async def test_without_a_position_nothing_happens(hass: HomeAssistant) -> None:
    """Test a valve that has not reported a position is left alone."""
    unknown = FakeValve("unknown", None)
    await _setup(hass, unknown)

    await _step(hass, "increase_position", "valve.unknown")

    assert not unknown.told


async def test_a_valve_without_positions_refuses(hass: HomeAssistant) -> None:
    """Test a valve that only opens and closes says so."""
    await _setup(hass, FakeShutoffValve("shutoff", None))

    with pytest.raises(ServiceNotSupported):
        await _step(hass, "increase_position", "valve.shutoff")


async def test_one_at_a_time_platforms_are_not_held_up(hass: HomeAssistant) -> None:
    """Test a platform that does one call at a time still gets the step."""
    valve = FakeValve("valve", 50)
    await _setup(hass, valve, parallel_updates=1)

    async with asyncio.timeout(5):
        await _step(hass, "increase_position", "valve.valve")

    assert valve.told == [60]
