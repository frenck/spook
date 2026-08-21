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


# Compared exactly rather than approximately, so it needs a name.
_ON_GRID_VALUE = 0.1


def _call(**data: Any) -> SimpleNamespace:
    """Build a service call, with the schema's cycle default applied."""
    return SimpleNamespace(data={"cycle": False, **data})


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
    call = _call(amount=0.5)

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
    call = _call(amount=0.3)

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
    call = _call(amount=50)

    await service_cls(hass).async_handle_service(entity, call)

    assert entity.set_value == expected


@pytest.mark.parametrize(
    "service_cls",
    [increment.SpookService, decrement.SpookService],
)
async def test_input_number_services_reject_near_multiples_of_large_steps(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
) -> None:
    """Test the tolerance stays absolute and does not grow with the step."""
    entity = MockInputNumber(0, step=1_000_000_000)
    call = _call(amount=999_999_999)

    with pytest.raises(ValueError, match="needs to be a multiple of"):
        await service_cls(hass).async_handle_service(entity, call)


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
    call = _call(amount=0.2)

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
    call = _call(amount=0.5)

    with pytest.raises(
        HomeAssistantError,
        match=escape("Value None for input_number.test is not a number"),
    ):
        await service_cls(hass).async_handle_service(entity, call)


@pytest.mark.parametrize(
    ("service_cls", "start", "amount", "expected"),
    [
        # 10.5 is one step past the maximum of 10, so it lands on the minimum.
        (increment.SpookService, 9.5, 1.0, 0.0),
        # Three steps past, so three steps up from the minimum.
        (increment.SpookService, 9.5, 2.0, 1.0),
        # One step below the minimum lands on the maximum.
        (decrement.SpookService, 0.5, 1.0, 10.0),
        (decrement.SpookService, 0.5, 2.0, 9.0),
    ],
)
async def test_cycling_carries_on_from_the_other_end(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    start: float,
    amount: float,
    expected: float,
) -> None:
    """Test overshooting the range continues from the other side.

    Home Assistant cycles a select by taking the new index modulo the number
    of options, so stepping two past the end lands two in from the other end
    rather than exactly on it.
    """
    entity = MockInputNumber(start)

    await service_cls(hass).async_handle_service(
        entity, _call(amount=amount, cycle=True)
    )

    assert entity.set_value == pytest.approx(expected)


@pytest.mark.parametrize(
    ("service_cls", "start", "expected"),
    [
        (increment.SpookService, 5, 10),
        (decrement.SpookService, 5, 0),
    ],
)
async def test_not_cycling_still_stops_at_the_end(
    hass: Any,
    service_cls: type[increment.SpookService | decrement.SpookService],
    start: float,
    expected: float,
) -> None:
    """Test the range is clamped when cycling was not asked for."""
    entity = MockInputNumber(start)

    await service_cls(hass).async_handle_service(entity, _call(amount=50))

    assert entity.set_value == expected


async def test_cycling_a_fractional_step_lands_exactly_on_the_grid(
    hass: Any,
) -> None:
    """Test wrapping leaves no float drift behind.

    Compared exactly on purpose. 0.9 + 0.3 is 1.2000000000000002, and running
    the modulo on that value rather than on whole steps gives
    0.09999999999999987. Both display as 0.1, so only an exact comparison says
    which one was stored.
    """
    entity = MockInputNumber(0.9, step=0.1)
    entity.native_max_value = 1

    await increment.SpookService(hass).async_handle_service(
        entity, _call(amount=0.3, cycle=True)
    )

    assert entity.set_value == _ON_GRID_VALUE


async def test_cycling_stays_in_range_when_the_step_does_not_fit(
    hass: Any,
) -> None:
    """Test wrapping cannot leave the range when the step divides it unevenly.

    A step of 0.3 across 0 to 1 puts the grid at 0, 0.3, 0.6 and 0.9, with the
    maximum not on it. Wrapping the value instead of the step count would give
    1.2 here, above the maximum, and setting that raises.
    """
    entity = MockInputNumber(0.9, step=0.3)
    entity.native_max_value = 1

    await increment.SpookService(hass).async_handle_service(
        entity, _call(amount=0.3, cycle=True)
    )

    assert entity.set_value == pytest.approx(0.0)
    assert entity.native_min_value <= entity.set_value <= entity.native_max_value
