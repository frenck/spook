"""Tests for the number increment and decrement services."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from re import escape

import pytest
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform, UnitOfElectricCurrent, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from custom_components.spook.ectoplasms.number.services import decrement, increment
from custom_components.spook.ectoplasms.number.stepping import async_set_shown_value
from custom_components.spook.services import SpookServiceManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
    from pytest_homeassistant_custom_component.typing import WebSocketGenerator


pytestmark = pytest.mark.usefixtures("spook_translations")


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
        ServiceValidationError,
        match=escape(
            "Amount 0.2 does not fit number.test, which moves in steps of 0.5. "
            "Use a multiple of 0.5, or leave the amount out to move one step"
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

    with pytest.raises(ServiceValidationError, match="Use a multiple of"):
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


async def test_a_shown_value_just_past_a_limit_lands_on_it(hass: Any) -> None:
    """Test rounding between units cannot carry a value past a native limit.

    86 °F is the top of 30 °C, but converting back can come out a hair above
    it, which the entity would refuse.
    """
    hass.config.units = US_CUSTOMARY_SYSTEM
    entity = _CelsiusShownAsFahrenheit()
    entity.hass = hass

    await async_set_shown_value(entity, 86.01)

    assert entity.native_value == entity.native_max_value


class _ChargeCurrent(NumberEntity):
    """A charger's charge current, set in steps of six amps."""

    _attr_should_poll = False
    _attr_name = "Charge current"
    _attr_unique_id = "charge_current"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 6
    _attr_native_max_value = 32
    _attr_native_step = 6
    _attr_native_value = 12

    async def async_set_native_value(self, value: float) -> None:
        """Keep what was set."""
        self._attr_native_value = value
        self.async_write_ha_state()


async def _setup_charger(hass: HomeAssistant, *, every_action: bool = False) -> None:
    """Set up an integration with a charge current number, and both actions.

    With every action, the way Spook sets them up: all its action modules
    loaded, `number.max` and `number.min` included.
    """
    assert await async_setup_component(hass, "homeassistant", {})

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.NUMBER])
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add([_ChargeCurrent()])

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    platform = MockPlatform(async_setup_entry=_setup_platform)
    # Locked, like most integrations that talk to a device.
    platform.PARALLEL_UPDATES = 1  # type: ignore[attr-defined]
    mock_platform(hass, "fake.number", platform)

    class _Flow(ConfigFlow, domain="fake"):
        """A config flow that does nothing."""

    with mock_config_flow("fake", _Flow):
        entry = MockConfigEntry(domain="fake")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    if every_action:
        manager = SpookServiceManager(hass)
        await manager.async_setup()
        await hass.async_block_till_done()
        return

    increment.SpookService(hass).async_register()
    decrement.SpookService(hass).async_register()


async def _run_from_the_frontend(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Run the action the way the frontend does, and return the answer."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "execute_script",
            "sequence": [
                {
                    "action": f"number.{service}",
                    "metadata": {},
                    "data": data,
                    "target": {"entity_id": "number.charge_current"},
                }
            ],
        }
    )
    return await client.receive_json()


@pytest.mark.parametrize("service", ["increment", "decrement"])
async def test_an_amount_off_the_step_says_why_in_the_frontend(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service: str,
) -> None:
    """Test the frontend shows why an amount is refused, not "Unknown error".

    The frontend runs an action through `execute_script`, which only passes
    the message on for a validation error. Anything else, like the
    `ValueError` this raised before, comes out as "Unknown error".
    """
    await _setup_charger(hass)

    response = await _run_from_the_frontend(
        hass, hass_ws_client, service, {"amount": 1}
    )

    assert not response["success"]
    assert response["error"]["code"] == "service_validation_error"
    assert response["error"]["message"] == (
        "Amount 1.0 does not fit number.charge_current, which moves in steps "
        "of 6. Use a multiple of 6, or leave the amount out to move one step"
    )
    assert hass.states.get("number.charge_current").state == "12"


@pytest.mark.parametrize(
    ("service", "data", "expected"),
    [
        ("increment", {}, 18),
        ("increment", {"amount": 12}, 24),
        ("decrement", {}, 6),
        # Stops at the minimum rather than going past it.
        ("decrement", {"amount": 12}, 6),
    ],
)
async def test_a_charger_steps_from_the_frontend(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service: str,
    data: dict[str, Any],
    expected: float,
) -> None:
    """Test stepping a real number from the frontend, on a locked platform."""
    await _setup_charger(hass)

    response = await _run_from_the_frontend(hass, hass_ws_client, service, data)

    assert response["success"], response
    assert float(hass.states.get("number.charge_current").state) == expected


@pytest.mark.parametrize(
    ("service", "data", "expected"),
    [
        ("increment", {}, 18),
        ("increment", {"amount": 12}, 24),
        ("decrement", {}, 6),
        ("decrement", {"amount": 12}, 6),
    ],
)
async def test_stepping_with_every_spook_action_loaded(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    service: str,
    data: dict[str, Any],
    expected: float,
) -> None:
    """Test stepping still works once Spook loaded all its actions.

    Loading `number.max` and `number.min` puts their modules on the package
    the stepping helper lives in, under the names of the built-ins it uses.
    The helper then called a module, and every step failed with "'module'
    object is not callable". #1944, and #1926 before it.
    """
    await _setup_charger(hass, every_action=True)

    response = await _run_from_the_frontend(hass, hass_ws_client, service, data)

    assert response["success"], response
    assert float(hass.states.get("number.charge_current").state) == expected
