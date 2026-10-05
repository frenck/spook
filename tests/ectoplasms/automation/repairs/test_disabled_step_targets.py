"""Tests for leaving disabled steps out of the target repairs.

Areas, devices, floors and labels, in automations and scripts alike. Home
Assistant's own lists include disabled steps, so each has to be subtracted.
"""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# What each repair takes as a reference, and an unknown one of that kind.
_KINDS = {
    "area": ("area_id", "xparked_area", "xbroken_area"),
    "floor": ("floor_id", "xparked_floor", "xbroken_floor"),
    "label": ("label_id", "xparked_label", "xbroken_label"),
    "device": (
        "device_id",
        "0000000000000000000000000000dead",
        "0000000000000000000000000000beef",
    ),
}


def _steps(key: str, parked: str, broken: str) -> list[dict[str, Any]]:
    """Return a parked step, and a reference both a parked and a running step use."""
    return [
        {
            "enabled": False,
            "action": "light.turn_on",
            "target": {key: parked},
        },
        {
            "enabled": False,
            "action": "light.turn_on",
            "target": {key: broken},
        },
        {"action": "light.turn_off", "target": {key: broken}},
    ]


async def _unknown(hass: HomeAssistant, domain: str, kind: str) -> set[str]:
    """Set up a real automation or script and ask the repair about it."""
    key, parked, broken = _KINDS[kind]
    if domain == "automation":
        config = {
            "automation": {
                "id": "parked",
                "alias": "parked",
                "triggers": [{"trigger": "event", "event_type": "go"}],
                "actions": _steps(key, parked, broken),
            }
        }
    else:
        config = {"script": {"parked": {"sequence": _steps(key, parked, broken)}}}

    assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()

    module = importlib.import_module(
        f"custom_components.spook.ectoplasms.{domain}.repairs.unknown_{kind}_references"
    )
    entity = hass.data[domain].get_entity(f"{domain}.parked")
    repair = module.SpookRepair(hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(entity)


@pytest.mark.parametrize("domain", ["automation", "script"])
@pytest.mark.parametrize("kind", list(_KINDS))
async def test_only_what_a_running_step_names_is_reported(
    hass: HomeAssistant, domain: str, kind: str
) -> None:
    """A parked step is left out; a reference a running step makes too is not."""
    _key, _parked, broken = _KINDS[kind]

    assert await _unknown(hass, domain, kind) == {broken}
