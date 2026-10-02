"""Tests for the number increment and decrement services."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from re import escape

import pytest
from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from custom_components.spook.ectoplasms.number.services import decrement, increment


class MockNumberEntity:  # pylint: disable=too-few-public-methods
    """Mock number entity."""

    entity_id = "number.test"
    max_value = 10
    min_value = 0
    native_max_value = 10
    native_min_value = 0
    step = 0.5

    def __init__(self, value: Any) -> None:
        """Initialize the mock number entity."""
        self.value = value
        self.set_value: float | None = None

    def convert_to_native_value(self, value: float) -> float:
        """Shown and native are the same units here."""
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value."""
        self.set_value = value


@pytest.mark.parametrize(
    ("service_cls", "start_value", "expected"),
    [
        (increment.SpookService, "1.5", 2.0),
        (decrement.SpookService, "1.5", 1.0),
    ],
)
async def test_number_services_handle_string_native_values(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    start_value: str,
    expected: float,
) -> None:
    """Test number services handle integrations exposing string native values."""
    entity = MockNumberEntity(start_value)
    call = SimpleNamespace(data={"amount": 0.5})

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.set_value == expected


@pytest.mark.parametrize(
    "service_cls",
    [increment.SpookService, decrement.SpookService],
)
async def test_number_services_raise_readable_error_for_invalid_amount(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
) -> None:
    """Test invalid amounts raise a readable error."""
    entity = MockNumberEntity(1.5)
    call = SimpleNamespace(data={"amount": 0.2})

    with pytest.raises(
        ValueError,
        match=escape(
            "Amount 0.2 not valid for number.test, it needs to be a multiple of 0.5"
        ),
    ):
        await service_cls(hass).async_handle_service(entity, call)


@pytest.mark.parametrize(
    "service_cls",
    [increment.SpookService, decrement.SpookService],
)
async def test_number_services_reject_near_multiples_of_large_steps(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
) -> None:
    """Test the tolerance stays absolute and does not grow with the step."""
    entity = MockNumberEntity(0)
    entity.step = 1_000_000_000
    call = SimpleNamespace(data={"amount": 999_999_999})

    with pytest.raises(ValueError, match="needs to be a multiple of"):
        await service_cls(hass).async_handle_service(entity, call)


@pytest.mark.parametrize(
    "service_cls",
    [increment.SpookService, decrement.SpookService],
)
async def test_number_services_raise_context_for_invalid_native_values(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
) -> None:
    """Test invalid native values raise an actionable error."""
    entity = MockNumberEntity("unavailable")
    call = SimpleNamespace(data={"amount": 0.5})

    with pytest.raises(
        HomeAssistantError,
        match=escape("Value 'unavailable' for number.test is not a number"),
    ):
        await service_cls(hass).async_handle_service(entity, call)


# 20 °C, the way a house set up in US units shows it.
_SHOWN_FAHRENHEIT = 68


class _CelsiusShownAsFahrenheit(NumberEntity):
    """A thermostat setpoint that keeps Celsius, in a house that reads °F."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 5
    _attr_native_max_value = 30
    _attr_native_step = 0.5
    _attr_native_value = 20
    entity_id = "number.setpoint"

    async def async_set_native_value(self, value: float) -> None:
        """Keep what was set, in Celsius."""
        self._attr_native_value = value


@pytest.mark.parametrize(
    ("service_cls", "expected_celsius"),
    [
        # 68 °F up one is 69 °F, which is 20.56 °C, not 69 °C.
        (increment.SpookService, 20.56),
        # 68 °F down one is 67 °F, which is 19.44 °C, not 67 °C (a rise).
        (decrement.SpookService, 19.44),
    ],
)
async def test_stepping_happens_in_the_units_somebody_sees(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    expected_celsius: float,
) -> None:
    """Test a step is taken in the shown units and lands in the kept ones.

    The amount is what the number shows its steps in, and so is its value.
    Handing the result over as if it were Celsius set a thermostat showing
    68 °F to 69 °C, and a decrement to 67 °C: warmer.
    """
    hass.config.units = US_CUSTOMARY_SYSTEM
    entity = _CelsiusShownAsFahrenheit()
    entity.hass = hass
    assert entity.value == _SHOWN_FAHRENHEIT

    await service_cls(hass).async_handle_service(
        entity, SimpleNamespace(data={"amount": 1})
    )

    assert entity.native_value == pytest.approx(expected_celsius, abs=0.01)
