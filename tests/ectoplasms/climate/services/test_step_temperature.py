"""Tests for the climate increase and decrease temperature actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio

from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
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

from custom_components.spook.ectoplasms.climate.services.decrease_temperature import (
    SpookService as DecreaseService,
)
from custom_components.spook.ectoplasms.climate.services.increase_temperature import (
    SpookService as IncreaseService,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )


class FakeThermostat(ClimateEntity):  # pylint: disable=too-many-instance-attributes
    """A thermostat with one setpoint, that remembers what it was told."""

    _attr_should_poll = False
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 7
    _attr_max_temp = 25

    def __init__(
        self,
        name: str,
        target: float | None,
        *,
        hvac_mode: HVACMode = HVACMode.HEAT,
        step: float | None = None,
    ) -> None:
        """Initialize the thermostat."""
        self._attr_name = name
        self._attr_unique_id = name
        self._attr_target_temperature = target
        self._attr_hvac_mode = hvac_mode
        self._attr_target_temperature_step = step
        self.told: list[dict[str, Any]] = []

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Take the new setpoints, leaving out who they were for."""
        self.told.append({k: v for k, v in kwargs.items() if k != "entity_id"})
        if ATTR_TEMPERATURE in kwargs:
            self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
        if "target_temp_low" in kwargs:
            self._attr_target_temperature_low = kwargs["target_temp_low"]
            self._attr_target_temperature_high = kwargs["target_temp_high"]
        self.async_write_ha_state()


class FakeFahrenheitThermostat(FakeThermostat):
    """A thermostat that works in Fahrenheit, in a house set to Celsius."""

    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _attr_min_temp = 45
    _attr_max_temp = 86


class FakeRangeThermostat(FakeThermostat):
    """A thermostat that heats below one setpoint and cools above another."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]

    def __init__(self, name: str, low: float, high: float) -> None:
        """Initialize the thermostat."""
        super().__init__(name, None, hvac_mode=HVACMode.HEAT_COOL)
        self._attr_target_temperature_low = low
        self._attr_target_temperature_high = high


class FakeDualThermostat(FakeThermostat):
    """A thermostat that does a single setpoint and a band, by mode."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.HEAT_COOL]

    def __init__(self, name: str, hvac_mode: HVACMode) -> None:
        """Initialize the thermostat, with all three setpoints reported."""
        super().__init__(name, 21.0, hvac_mode=hvac_mode, step=1.0)
        self._attr_target_temperature_low = 19.0
        self._attr_target_temperature_high = 23.0


class FakeFan(FakeThermostat):
    """A climate device with nothing but a fan, and no setpoint at all."""

    _attr_supported_features = ClimateEntityFeature.FAN_MODE
    _attr_fan_modes = ["low", "high"]
    _attr_fan_mode = "low"


async def _setup(
    hass: HomeAssistant, *thermostats: ClimateEntity, parallel_updates: int = 0
) -> None:
    """Set up these thermostats and both actions."""
    assert await async_setup_component(hass, "homeassistant", {})

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.CLIMATE])
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add(list(thermostats))

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    platform = MockPlatform(async_setup_entry=_setup_platform)
    if parallel_updates:
        platform.PARALLEL_UPDATES = parallel_updates  # type: ignore[attr-defined]
    mock_platform(hass, "fake.climate", platform)

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
    """Step a thermostat."""
    await hass.services.async_call(
        "climate", service, {"entity_id": entity_id, **data}, blocking=True
    )


async def test_one_setpoint_goes_up_by_the_thermostats_own_step(
    hass: HomeAssistant,
) -> None:
    """Test the step the thermostat reports is the one used."""
    living = FakeThermostat("living", 20.0, step=1.0)
    await _setup(hass, living)

    await _step(hass, "increase_temperature", "climate.living")

    assert living.told == [{ATTR_TEMPERATURE: 21.0}]


async def test_without_a_step_of_its_own_half_a_degree_is_used(
    hass: HomeAssistant,
) -> None:
    """Test the interface's own fallback, half a degree in Celsius."""
    living = FakeThermostat("living", 20.0)
    await _setup(hass, living)

    await _step(hass, "decrease_temperature", "climate.living")

    assert living.told == [{ATTR_TEMPERATURE: 19.5}]


async def test_a_step_asked_for_wins_and_adds_up_cleanly(
    hass: HomeAssistant,
) -> None:
    """Test a given step overrides the thermostat's, without float noise."""
    living = FakeThermostat("living", 21.4, step=1.0)
    await _setup(hass, living)

    # 21.4 - 0.3 is 21.099999999999998 in floats.
    await _step(hass, "decrease_temperature", "climate.living", step=0.3)

    assert living.told == [{ATTR_TEMPERATURE: 21.1}]


async def test_the_limits_are_kept(hass: HomeAssistant) -> None:
    """Test a step stops at the limit, and one at the limit does nothing."""
    almost = FakeThermostat("almost", 24.5, step=1.0)
    maxed = FakeThermostat("maxed", 25.0, step=1.0)
    await _setup(hass, almost, maxed)

    await _step(hass, "increase_temperature", "climate.almost")
    await _step(hass, "increase_temperature", "climate.maxed")

    assert almost.told == [{ATTR_TEMPERATURE: 25.0}]
    assert not maxed.told


async def test_past_a_limit_warmer_is_never_colder(hass: HomeAssistant) -> None:
    """Test a thermostat already past its maximum is not pulled back down.

    Some integrations report a setpoint beyond the limits they report too.
    """
    beyond = FakeThermostat("beyond", 28.0, step=1.0)
    await _setup(hass, beyond)

    await _step(hass, "increase_temperature", "climate.beyond")

    assert not beyond.told


async def test_two_setpoints_move_together(hass: HomeAssistant) -> None:
    """Test heating and cooling setpoints both move, keeping their band."""
    house = FakeRangeThermostat("house", 19.0, 23.0)
    await _setup(hass, house)

    await _step(hass, "increase_temperature", "climate.house", step=1)

    assert house.told == [{"target_temp_low": 20.0, "target_temp_high": 24.0}]


async def test_a_band_stops_whole_at_a_limit(hass: HomeAssistant) -> None:
    """Test the band keeps its width when one side reaches a limit.

    Squeezing it would leave a thermostat heating and cooling ever closer
    together.
    """
    house = FakeRangeThermostat("house", 20.0, 24.5)
    await _setup(hass, house)

    await _step(hass, "increase_temperature", "climate.house", step=1)

    assert house.told == [{"target_temp_low": 20.5, "target_temp_high": 25.0}]


async def test_a_thermostat_that_is_off_is_adjusted_not_switched(
    hass: HomeAssistant,
) -> None:
    """Test a thermostat that is off gets its setpoint and stays off."""
    attic = FakeThermostat("attic", 15.0, hvac_mode=HVACMode.OFF, step=1.0)
    await _setup(hass, attic)

    await _step(hass, "increase_temperature", "climate.attic")

    assert attic.told == [{ATTR_TEMPERATURE: 16.0}]
    assert hass.states.get("climate.attic").state == HVACMode.OFF


async def test_without_a_setpoint_nothing_happens(hass: HomeAssistant) -> None:
    """Test a thermostat with no setpoint reported yet is left alone."""
    unknown = FakeThermostat("unknown", None)
    await _setup(hass, unknown)

    await _step(hass, "increase_temperature", "climate.unknown")

    assert not unknown.told


async def test_a_device_without_setpoints_refuses(hass: HomeAssistant) -> None:
    """Test a climate device that only does fan speeds says so."""
    await _setup(hass, FakeFan("fan", None))

    with pytest.raises(ServiceNotSupported):
        await _step(hass, "increase_temperature", "climate.fan")


@pytest.mark.parametrize(
    ("hvac_mode", "expected"),
    [
        (HVACMode.HEAT_COOL, {"target_temp_low": 20.0, "target_temp_high": 24.0}),
        (HVACMode.HEAT, {ATTR_TEMPERATURE: 22.0}),
    ],
)
async def test_the_band_moves_in_heat_cool_mode(
    hass: HomeAssistant, hvac_mode: HVACMode, expected: dict[str, float]
) -> None:
    """Test a thermostat reporting both moves the one its mode uses."""
    both = FakeDualThermostat("both", hvac_mode)
    await _setup(hass, both)

    await _step(hass, "increase_temperature", "climate.both")

    assert both.told == [expected]


@pytest.mark.parametrize(
    ("service", "target"),
    [("increase_temperature", 5.0), ("decrease_temperature", 28.0)],
)
async def test_a_setpoint_past_a_limit_is_left_alone(
    hass: HomeAssistant, service: str, target: float
) -> None:
    """Test a setpoint outside the limits is not jumped back inside.

    Five turned up by one, with a minimum of seven, would be sent seven.
    """
    outside = FakeThermostat("outside", target, step=1.0)
    await _setup(hass, outside)

    await _step(hass, service, "climate.outside")

    assert not outside.told


@pytest.mark.parametrize(
    ("service", "low", "high"),
    [("increase_temperature", 6.0, 25.0), ("decrease_temperature", 7.0, 26.0)],
)
async def test_a_band_past_a_limit_is_left_alone(
    hass: HomeAssistant, service: str, low: float, high: float
) -> None:
    """Test a band already outside the limits is not pushed further out.

    With limits of seven to twenty-five, turning up six to twenty-five would
    otherwise send seven to twenty-six.
    """
    outside = FakeRangeThermostat("outside", low, high)
    await _setup(hass, outside)

    await _step(hass, service, "climate.outside")

    assert not outside.told


async def test_a_step_in_fahrenheit_is_one_in_fahrenheit(hass: HomeAssistant) -> None:
    """Test a thermostat's own step is taken in its own unit.

    Home Assistant shows every temperature in its own unit, except the step.
    One degree Fahrenheit read as one degree Celsius would be nearly two.
    """
    american = FakeFahrenheitThermostat("american", 68.0, step=1.0)
    await _setup(hass, american)

    await _step(hass, "increase_temperature", "climate.american")

    # Exactly, not 69.008: worked out in Fahrenheit, never turned into
    # Celsius and back.
    assert american.told == [{ATTR_TEMPERATURE: 69.0}]


async def test_one_at_a_time_platforms_are_not_held_up(hass: HomeAssistant) -> None:
    """Test a platform that updates one entity at a time still gets the step.

    The action hands the change on to `climate.set_temperature`. Home
    Assistant only holds a platform's update lock while polling, not while
    running an action, so that call does not wait on the action around it.
    """
    living = FakeThermostat("living", 20.0, step=1.0)
    await _setup(hass, living, parallel_updates=1)

    async with asyncio.timeout(5):
        await _step(hass, "increase_temperature", "climate.living")

    assert living.told == [{ATTR_TEMPERATURE: 21.0}]


async def test_a_fahrenheit_limit_is_kept_exactly(hass: HomeAssistant) -> None:
    """Test a thermostat's own limit is met, not missed by rounding.

    Through Celsius, a minimum of 45 comes back as 44.996, just past a limit
    the thermostat may refuse.
    """
    american = FakeFahrenheitThermostat("american", 45.5, step=1.0)
    await _setup(hass, american)

    await _step(hass, "decrease_temperature", "climate.american")

    assert american.told == [{ATTR_TEMPERATURE: 45.0}]


async def test_a_step_asked_for_is_in_home_assistants_unit(
    hass: HomeAssistant,
) -> None:
    """Test a step given in Celsius moves a Fahrenheit thermostat as far."""
    american = FakeFahrenheitThermostat("american", 68.0, step=1.0)
    await _setup(hass, american)

    await _step(hass, "increase_temperature", "climate.american", step=1)

    assert american.told == [{ATTR_TEMPERATURE: 69.8}]
