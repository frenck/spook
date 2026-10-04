"""Tests for the humidifier increase and decrease humidity actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from custom_components.spook.ectoplasms.humidifier.services.decrease_humidity import (
    SpookService as DecreaseService,
)
from custom_components.spook.ectoplasms.humidifier.services.increase_humidity import (
    SpookService as IncreaseService,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )


class FakeHumidifier(HumidifierEntity):
    """A humidifier that remembers what it was told."""

    _attr_should_poll = False
    _attr_is_on = True
    _attr_min_humidity = 30
    _attr_max_humidity = 70

    def __init__(
        self, name: str, target: float | None, step: float | None = None
    ) -> None:
        """Initialize the humidifier."""
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_target_humidity = target
        self._attr_target_humidity_step = step
        self.told: list[int] = []

    async def async_set_humidity(self, humidity: int) -> None:
        """Take the new target."""
        self.told.append(humidity)
        self._attr_target_humidity = humidity
        self.async_write_ha_state()


async def _setup(
    hass: HomeAssistant, *humidifiers: HumidifierEntity, parallel_updates: int = 0
) -> None:
    """Set up these humidifiers and both actions."""
    assert await async_setup_component(hass, "homeassistant", {})

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform.HUMIDIFIER]
        )
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add(list(humidifiers))

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    platform = MockPlatform(async_setup_entry=_setup_platform)
    if parallel_updates:
        platform.PARALLEL_UPDATES = parallel_updates  # type: ignore[attr-defined]
    mock_platform(hass, "fake.humidifier", platform)

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
    """Step a humidifier."""
    await hass.services.async_call(
        "humidifier", service, {"entity_id": entity_id, **data}, blocking=True
    )


async def test_one_percent_without_a_step_of_its_own(hass: HomeAssistant) -> None:
    """Test the interface's own fallback, one percent."""
    bedroom = FakeHumidifier("bedroom", 45)
    await _setup(hass, bedroom)

    await _step(hass, "increase_humidity", "humidifier.bedroom")

    assert bedroom.told == [46]


async def test_its_own_step_and_a_given_one(hass: HomeAssistant) -> None:
    """Test the humidifier's own step, and a given one winning over it."""
    bedroom = FakeHumidifier("bedroom", 45, step=5)
    await _setup(hass, bedroom)

    await _step(hass, "decrease_humidity", "humidifier.bedroom")
    await _step(hass, "decrease_humidity", "humidifier.bedroom", step=2)

    assert bedroom.told == [40, 38]


async def test_the_limits_are_kept(hass: HomeAssistant) -> None:
    """Test a step stops at the limit, and one at the limit does nothing."""
    almost = FakeHumidifier("almost", 68, step=5)
    maxed = FakeHumidifier("maxed", 70, step=5)
    await _setup(hass, almost, maxed)

    await _step(hass, "increase_humidity", "humidifier.almost")
    await _step(hass, "increase_humidity", "humidifier.maxed")

    assert almost.told == [70]
    assert not maxed.told


async def test_past_a_limit_it_is_left_alone(hass: HomeAssistant) -> None:
    """Test a target already past a limit is not jumped back inside."""
    beyond = FakeHumidifier("beyond", 20, step=5)
    await _setup(hass, beyond)

    await _step(hass, "increase_humidity", "humidifier.beyond")

    assert not beyond.told


async def test_a_step_of_part_of_a_percent_is_a_whole_one(
    hass: HomeAssistant,
) -> None:
    """Test a humidifier's own half-percent step moves a whole percent.

    Home Assistant hands a humidifier whole percentages, so half a percent
    would round to a whole step one time and to none the next.
    """
    fine = FakeHumidifier("fine", 45, step=0.5)
    await _setup(hass, fine)

    await _step(hass, "decrease_humidity", "humidifier.fine")
    await _step(hass, "increase_humidity", "humidifier.fine")
    await _step(hass, "increase_humidity", "humidifier.fine")

    assert fine.told == [44, 45, 46]


async def test_without_a_target_nothing_happens(hass: HomeAssistant) -> None:
    """Test a humidifier with no target reported yet is left alone."""
    unknown = FakeHumidifier("unknown", None)
    await _setup(hass, unknown)

    await _step(hass, "increase_humidity", "humidifier.unknown")

    assert not unknown.told


async def test_one_at_a_time_platforms_are_not_held_up(hass: HomeAssistant) -> None:
    """Test a platform that does one call at a time still gets the step."""
    bedroom = FakeHumidifier("bedroom", 45)
    await _setup(hass, bedroom, parallel_updates=1)

    async with asyncio.timeout(5):
        await _step(hass, "increase_humidity", "humidifier.bedroom")

    assert bedroom.told == [46]


async def test_a_step_with_a_fraction_is_refused(hass: HomeAssistant) -> None:
    """Test 5.9 is refused, rather than quietly taken as 5."""
    await _setup(hass, FakeHumidifier("bedroom", 45))

    with pytest.raises(vol.Invalid):
        await _step(hass, "increase_humidity", "humidifier.bedroom", step=5.9)
