"""Tests for target references nested in repeat sequences.

Home Assistant's built-in ``referenced_*`` extraction misses ``repeat``
step types entirely; the automation reference repairs compensate by also
walking the raw configuration.
"""

# pylint: disable=wrong-import-order,protected-access
# ruff: noqa: SLF001
from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from custom_components.spook.entity_filtering import (
    async_get_template_area_lookup,
    async_get_template_floor_lookup,
    async_get_template_label_lookup,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# What the template lookups of each kind resolve against.
_TEMPLATE_LOOKUPS = {
    "area": async_get_template_area_lookup,
    "floor": async_get_template_floor_lookup,
    "label": async_get_template_label_lookup,
}


def _raw_config_with_repeat_nested(key: str, value: str) -> dict:
    """Return an automation config with a target nested in a repeat."""
    return {
        "actions": [
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
        "custom_components.spook.ectoplasms.automation.repairs."
        f"unknown_{reference_type}_references",
    )
    repair = module.SpookRepair(hass)
    setattr(repair, f"_known_{reference_type}_ids", {"known"})
    # Standing in for `_async_setup_inspection`: what the template lookups
    # resolve against, from registries that hold nothing here.
    if reference_type in _TEMPLATE_LOOKUPS:
        repair._template_lookup = _TEMPLATE_LOOKUPS[reference_type](hass)

    entity = SimpleNamespace(
        raw_config=_raw_config_with_repeat_nested(f"{reference_type}_id", ghost_id),
        **{f"referenced_{reference_type}s": set()},
    )

    assert await repair._async_compute_unknown_references(entity) == {ghost_id}
