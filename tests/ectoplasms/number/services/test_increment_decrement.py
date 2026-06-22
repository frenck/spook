"""Tests for the number increment and decrement services."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from re import escape

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.spook.ectoplasms.number.services import decrement, increment


class MockNumberEntity:  # pylint: disable=too-few-public-methods
    """Mock number entity."""

    entity_id = "number.test"
    max_value = 10
    min_value = 0
    step = 0.5

    def __init__(self, value: Any) -> None:
        """Initialize the mock number entity."""
        self.value = value
        self.set_value: float | None = None

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
async def test_number_services_raise_context_for_invalid_native_values(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
) -> None:
    """Test invalid native values raise an actionable error."""
    entity = MockNumberEntity("unavailable")
    call = SimpleNamespace(data={"amount": 0.5})

    with pytest.raises(
        HomeAssistantError,
        match=escape("Native value 'unavailable' for number.test is not a number"),
    ):
        await service_cls(hass).async_handle_service(entity, call)
