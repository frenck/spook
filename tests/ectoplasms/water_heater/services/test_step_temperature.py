"""Tests for the water heater increase and decrease temperature actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
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

from custom_components.spook.ectoplasms.water_heater.services.decrease_temperature import (
    SpookService as DecreaseService,
)
from custom_components.spook.ectoplasms.water_heater.services.increase_temperature import (
    SpookService as IncreaseService,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )


class FakeWaterHeater(WaterHeaterEntity):
    """A water heater that remembers what it was told."""

    _attr_should_poll = False
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 40
    _attr_max_temp = 65

    def __init__(
        self, name: str, target: float | None, step: float | None = None
    ) -> None:
        """Initialize the water heater."""
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_target_temperature = target
        self._attr_target_temperature_step = step
        self.told: list[dict[str, Any]] = []

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Take the new setpoint, leaving out who it was for."""
        self.told.append({k: v for k, v in kwargs.items() if k != "entity_id"})
        self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
        self.async_write_ha_state()


class FakeFahrenheitWaterHeater(FakeWaterHeater):
    """A water heater in Fahrenheit, in a house set to Celsius."""

    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 100
    _attr_max_temp = 150


class FakeOnOffWaterHeater(FakeWaterHeater):
    """A water heater that can only be switched, with no setpoint at all."""

    _attr_supported_features = WaterHeaterEntityFeature.ON_OFF


async def _setup(
    hass: HomeAssistant, *heaters: WaterHeaterEntity, parallel_updates: int = 0
) -> None:
    """Set up these water heaters and both actions."""
    assert await async_setup_component(hass, "homeassistant", {})

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform.WATER_HEATER]
        )
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add(list(heaters))

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    platform = MockPlatform(async_setup_entry=_setup_platform)
    if parallel_updates:
        platform.PARALLEL_UPDATES = parallel_updates  # type: ignore[attr-defined]
    mock_platform(hass, "fake.water_heater", platform)

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
    """Step a water heater."""
    await hass.services.async_call(
        "water_heater", service, {"entity_id": entity_id, **data}, blocking=True
    )


async def test_the_setpoint_goes_up_by_its_own_step(hass: HomeAssistant) -> None:
    """Test the step the water heater reports is the one used."""
    boiler = FakeWaterHeater("boiler", 55.0, step=1.0)
    await _setup(hass, boiler)

    await _step(hass, "increase_temperature", "water_heater.boiler")

    assert boiler.told == [{ATTR_TEMPERATURE: 56.0}]


async def test_without_a_step_of_its_own_half_a_degree_is_used(
    hass: HomeAssistant,
) -> None:
    """Test the interface's own fallback, half a degree in Celsius."""
    boiler = FakeWaterHeater("boiler", 55.0)
    await _setup(hass, boiler)

    await _step(hass, "decrease_temperature", "water_heater.boiler")

    assert boiler.told == [{ATTR_TEMPERATURE: 54.5}]


async def test_the_limits_are_kept(hass: HomeAssistant) -> None:
    """Test a step stops at the limit, and one at the limit does nothing."""
    almost = FakeWaterHeater("almost", 64.5, step=1.0)
    maxed = FakeWaterHeater("maxed", 65.0, step=1.0)
    await _setup(hass, almost, maxed)

    await _step(hass, "increase_temperature", "water_heater.almost")
    await _step(hass, "increase_temperature", "water_heater.maxed")

    assert almost.told == [{ATTR_TEMPERATURE: 65.0}]
    assert not maxed.told


async def test_past_a_limit_it_is_left_alone(hass: HomeAssistant) -> None:
    """Test a setpoint already past a limit is not jumped back inside."""
    beyond = FakeWaterHeater("beyond", 30.0, step=1.0)
    await _setup(hass, beyond)

    await _step(hass, "increase_temperature", "water_heater.beyond")

    assert not beyond.told


async def test_fahrenheit_stays_fahrenheit(hass: HomeAssistant) -> None:
    """Test a water heater in Fahrenheit is stepped in Fahrenheit, exactly."""
    american = FakeFahrenheitWaterHeater("american", 120.0, step=1.0)
    await _setup(hass, american)

    await _step(hass, "increase_temperature", "water_heater.american")
    await _step(hass, "increase_temperature", "water_heater.american", step=1)

    assert american.told == [{ATTR_TEMPERATURE: 121.0}, {ATTR_TEMPERATURE: 122.8}]


async def test_without_a_setpoint_nothing_happens(hass: HomeAssistant) -> None:
    """Test a water heater with no setpoint reported yet is left alone."""
    unknown = FakeWaterHeater("unknown", None)
    await _setup(hass, unknown)

    await _step(hass, "increase_temperature", "water_heater.unknown")

    assert not unknown.told


async def test_a_water_heater_without_a_setpoint_refuses(hass: HomeAssistant) -> None:
    """Test a water heater that can only be switched says so."""
    await _setup(hass, FakeOnOffWaterHeater("switch", None))

    with pytest.raises(ServiceNotSupported):
        await _step(hass, "increase_temperature", "water_heater.switch")


async def test_one_at_a_time_platforms_are_not_held_up(hass: HomeAssistant) -> None:
    """Test a platform that does one call at a time still gets the step."""
    boiler = FakeWaterHeater("boiler", 55.0, step=1.0)
    await _setup(hass, boiler, parallel_updates=1)

    async with asyncio.timeout(5):
        await _step(hass, "increase_temperature", "water_heater.boiler")

    assert boiler.told == [{ATTR_TEMPERATURE: 56.0}]
