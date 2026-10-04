"""Tests for the shared setpoint stepping."""

from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol

from custom_components.spook.setpoints import whole_percent


@pytest.mark.parametrize(
    ("value", "expected"), [(5, 5), ("5", 5), (5.0, 5), ("5.0", 5)]
)
def test_a_whole_number_is_taken_as_it_is_written(value: Any, expected: int) -> None:
    """Test a whole number passes, however it is written."""
    assert whole_percent(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        5.9,
        "5.9",
        0.5,
        "5.0000000000000001",
        True,
        "five",
        None,
        "inf",
        "nan",
        0,
        101,
        "1e1000000000",
    ],
)
def test_anything_else_is_refused_not_cut_down(value: Any) -> None:
    """Test a fraction, a bool, no number, or too much is refused.

    `5.0000000000000001` is exactly 5.0 as a float, and `True` is 1 as an int:
    both would round or slip their way through without care. The last one is
    refused as too large without ever being built as an integer.
    """
    with pytest.raises(vol.Invalid):
        whole_percent(value)
