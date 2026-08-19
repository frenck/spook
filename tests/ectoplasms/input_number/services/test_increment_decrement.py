"""Tests for the input number increment and decrement services."""

from __future__ import annotations

from re import escape
from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.spook.ectoplasms.input_number.services import (
    decrement,
    increment,
)


class MockInputNumber:  # pylint: disable=too-few-public-methods
    """Mock input number entity."""

    entity_id = "input_number.test"
    native_min_value = 0
    native_max_value = 10

    def __init__(self, value: Any, step: float = 0.5) -> None:
        """Initialize the mock input number entity."""
        self.native_value = value
        self.native_step = step
        self.set_value: float | None = None

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value."""
        self.set_value = value


@pytest.mark.parametrize(
    ("service_cls", "expected"),
    [
        (increment.SpookService, 2.0),
        (decrement.SpookService, 1.0),
    ],
)
async def test_input_number_services_apply_amount(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    expected: float,
) -> None:
    """Test the services apply the requested amount."""
    entity = MockInputNumber(1.5)
    call = SimpleNamespace(data={"amount": 0.5})

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.set_value == expected


@pytest.mark.parametrize(
    ("service_cls", "expected"),
    [
        (increment.SpookService, 2.0),
        (decrement.SpookService, 1.0),
    ],
)
async def test_input_number_services_fall_back_to_the_step(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    expected: float,
) -> None:
    """Test the services step by the entity step when no amount is given."""
    entity = MockInputNumber(1.5)
    call = SimpleNamespace(data={})

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.set_value == expected


@pytest.mark.parametrize(
    ("service_cls", "expected"),
    [
        (increment.SpookService, 1.8),
        (decrement.SpookService, 1.2),
    ],
)
async def test_input_number_services_accept_float_multiples(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    expected: float,
) -> None:
    """Test amounts that float modulo cannot divide cleanly are accepted."""
    entity = MockInputNumber(1.5, step=0.1)
    call = SimpleNamespace(data={"amount": 0.3})

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.set_value == pytest.approx(expected)


@pytest.mark.parametrize(
    ("service_cls", "expected"),
    [
        (increment.SpookService, 10),
        (decrement.SpookService, 0),
    ],
)
async def test_input_number_services_stay_within_range(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    expected: float,
) -> None:
    """Test the services clamp to the configured minimum and maximum."""
    entity = MockInputNumber(5)
    call = SimpleNamespace(data={"amount": 50})

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.set_value == expected


@pytest.mark.parametrize(
    "service_cls",
    [increment.SpookService, decrement.SpookService],
)
async def test_input_number_services_raise_readable_error_for_invalid_amount(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
) -> None:
    """Test invalid amounts raise a readable error."""
    entity = MockInputNumber(1.5)
    call = SimpleNamespace(data={"amount": 0.2})

    with pytest.raises(
        ValueError,
        match=escape(
            "Amount 0.2 not valid for input_number.test, "
            "it needs to be a multiple of 0.5"
        ),
    ):
        await service_cls(hass).async_handle_service(entity, call)


@pytest.mark.parametrize(
    "service_cls",
    [increment.SpookService, decrement.SpookService],
)
async def test_input_number_services_raise_context_for_missing_values(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
) -> None:
    """Test a missing current value raises an actionable error."""
    entity = MockInputNumber(None)
    call = SimpleNamespace(data={"amount": 0.5})

    with pytest.raises(
        HomeAssistantError,
        match=escape("Value None for input_number.test is not a number"),
    ):
        await service_cls(hass).async_handle_service(entity, call)
