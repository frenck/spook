"""Tests for the shared setpoint stepping."""

from __future__ import annotations

from typing import Any

import pytest
import voluptuous as vol

from custom_components.spook.setpoints import whole_number


@pytest.mark.parametrize(
    ("value", "expected"), [(5, 5), ("5", 5), (5.0, 5), ("5.0", 5)]
)
def test_a_whole_number_is_taken_as_it_is_written(value: Any, expected: int) -> None:
    """Test a whole number passes, however it is written."""
    assert whole_number(value) == expected


@pytest.mark.parametrize("value", [5.9, "5.9", 0.5, "five", None])
def test_anything_else_is_refused_not_cut_down(value: Any) -> None:
    """Test a fraction is refused, not quietly cut down to the whole below."""
    with pytest.raises(vol.Invalid):
        whole_number(value)
