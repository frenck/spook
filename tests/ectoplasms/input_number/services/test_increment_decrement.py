"""Tests for the input number increment and decrement services."""
# pylint: disable=protected-access

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from re import escape

import pytest

from custom_components.spook.ectoplasms.input_number.services import (
    decrement,
    increment,
)


class MockInputNumberEntity:  # pylint: disable=too-few-public-methods
    """Mock input number entity."""

    entity_id = "input_number.test"
    _maximum = 10
    _minimum = 0
    _step = 0.5

    def __init__(self, value: float) -> None:
        """Initialize the mock input number entity."""
        self._current_value = value
        self.value: float | None = None

    async def async_set_value(self, value: float) -> None:
        """Set the value."""
        self.value = value


@pytest.mark.parametrize(
    ("service_cls", "start_value", "amount", "expected"),
    [
        (increment.SpookService, 9.5, 0.5, 10),
        (increment.SpookService, 9.5, 1, 10),
        (decrement.SpookService, 0.5, 0.5, 0),
        (decrement.SpookService, 0.5, 1, 0),
    ],
)
async def test_input_number_services_clamp_at_range(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    start_value: float,
    amount: float,
    expected: float,
) -> None:
    """Test input number services keep the existing clamping behavior."""
    entity = MockInputNumberEntity(start_value)
    call = SimpleNamespace(data={"amount": amount, "cycle": False})

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.value == expected


@pytest.mark.parametrize(
    ("service_cls", "start_value", "amount", "expected"),
    [
        (increment.SpookService, 9.5, 1, 0),
        (decrement.SpookService, 0.5, 1, 10),
    ],
)
async def test_input_number_services_cycle_at_range(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    start_value: float,
    amount: float,
    expected: float,
) -> None:
    """Test input number services can cycle past their range."""
    entity = MockInputNumberEntity(start_value)
    call = SimpleNamespace(data={"amount": amount, "cycle": True})

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.value == expected


@pytest.mark.parametrize(
    "service_cls",
    [increment.SpookService, decrement.SpookService],
)
async def test_input_number_services_raise_readable_error_for_invalid_amount(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
) -> None:
    """Test invalid amounts raise a readable error."""
    entity = MockInputNumberEntity(1.5)
    call = SimpleNamespace(data={"amount": 0.2, "cycle": False})

    with pytest.raises(
        ValueError,
        match=escape(
            "Amount 0.2 not valid for input_number.test, "
            "it needs to be a multiple of 0.5"
        ),
    ):
        await service_cls(hass).async_handle_service(entity, call)
