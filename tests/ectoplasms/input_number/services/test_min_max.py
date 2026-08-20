"""Tests for the input number min and max services."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.spook.ectoplasms.input_number.services import max as max_service
from custom_components.spook.ectoplasms.input_number.services import min as min_service


class MockInputNumber:  # pylint: disable=too-few-public-methods
    """Mock input number entity."""

    entity_id = "input_number.test"
    native_min_value = 1
    native_max_value = 9
    native_value = 5

    def __init__(self) -> None:
        """Initialize the mock input number entity."""
        self.set_value: float | None = None

    async def async_set_native_value(self, value: float) -> None:
        """Set the native value."""
        self.set_value = value


@pytest.mark.parametrize(
    ("service_cls", "expected"),
    [
        (min_service.SpookService, 1),
        (max_service.SpookService, 9),
    ],
)
async def test_input_number_min_max_services(
    hass: Any,
    service_cls: type[min_service.SpookService | max_service.SpookService],
    expected: float,
) -> None:
    """Test the services set the configured minimum and maximum."""
    entity = MockInputNumber()
    call = SimpleNamespace(data={})

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.set_value == expected
