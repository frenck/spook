"""Tests for target references nested in repeat sequences.

Home Assistant's built-in ``referenced_*`` extraction misses ``repeat``
step types entirely; the script reference repairs compensate by also
walking the raw configuration.
"""

# pylint: disable=wrong-import-order,protected-access
# ruff: noqa: SLF001
from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _raw_config_with_repeat_nested(key: str, value: str) -> dict:
    """Return a script config with a target nested in a repeat."""
    return {
        "sequence": [
            {
                "repeat": {
                    "count": 2,
                    "sequence": [
                        {
                            "action": "light.turn_on",
                            "target": {key: value},
                        },
                    ],
                },
            },
        ],
    }


@pytest.mark.parametrize(
    ("reference_type", "ghost_id"),
    [
        pytest.param("area", "ghost_area", id="area"),
        pytest.param("device", "abcdef0123456789abcdef0123456789", id="device"),
        pytest.param("floor", "ghost_floor", id="floor"),
        pytest.param("label", "ghost_label", id="label"),
    ],
)
async def test_repeat_nested_reference_is_detected(
    hass: HomeAssistant,
    reference_type: str,
    ghost_id: str,
) -> None:
    """Test a stale target inside a repeat sequence is reported."""
    module = importlib.import_module(
        "custom_components.spook.ectoplasms.script.repairs."
        f"unknown_{reference_type}_references",
    )
    repair = module.SpookRepair(hass)
    setattr(repair, f"_known_{reference_type}_ids", {"known"})

    entity = SimpleNamespace(
        raw_config=_raw_config_with_repeat_nested(f"{reference_type}_id", ghost_id),
        script=SimpleNamespace(**{f"referenced_{reference_type}s": set()}),
    )

    assert await repair._async_compute_unknown_references(entity) == {ghost_id}
