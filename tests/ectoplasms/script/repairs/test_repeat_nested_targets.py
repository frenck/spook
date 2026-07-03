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

from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


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


async def test_repeat_nested_target_detected_on_real_script_entity(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test detection against a real script entity, end to end.

    Pins that production ``ScriptEntity`` instances expose ``raw_config``;
    a mock-only test could keep passing if that attribute ever went away.
    """
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "spooky": {
                    "sequence": [
                        {
                            "repeat": {
                                "count": 2,
                                "sequence": [
                                    {
                                        "action": "light.turn_on",
                                        "target": {"area_id": "ghost_area"},
                                    },
                                ],
                            },
                        },
                    ],
                },
            },
        },
    )
    await hass.async_block_till_done()

    module = importlib.import_module(
        "custom_components.spook.ectoplasms.script.repairs.unknown_area_references",
    )
    repair = module.SpookRepair(hass)
    await repair.async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "script_unknown_area_references_script.spooky",
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["areas"] == "- `ghost_area`"
