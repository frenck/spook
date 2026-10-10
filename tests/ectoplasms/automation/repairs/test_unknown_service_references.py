"""Tests for automation unknown service reference repairs."""

# pylint: disable=protected-access

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.automation.repairs.unknown_service_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def test_automation_unknown_service_repair_inspects_when_components_load() -> None:
    """Test automation service references are rechecked when components load."""
    assert EVENT_COMPONENT_LOADED in SpookRepair.inspect_events


async def _unknown_in_automation(
    hass: HomeAssistant, actions: list[dict[str, Any]]
) -> set[str]:
    """Set up a real automation and ask the repair about it."""
    hass.services.async_register("light", "turn_on", lambda _call: None)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "garage",
                "alias": "garage",
                "triggers": [{"trigger": "event", "event_type": "arrived"}],
                "actions": actions,
            }
        },
    )
    await hass.async_block_till_done()

    entity = hass.data["automation"].get_entity("automation.garage")
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()  # noqa: SLF001
    return await repair._async_compute_unknown_references(entity)  # noqa: SLF001


async def test_actions_in_a_sequence_block_are_checked(hass: HomeAssistant) -> None:
    """The editor's "sequence" building block runs its steps like any other."""
    actions = [
        {
            "sequence": [
                {"action": "light.turn_on"},
                {"delay": 0},
                {"action": "cover.xopen_garage"},
                {"sequence": [{"action": "light.xdeeper"}]},
            ]
        }
    ]

    assert await _unknown_in_automation(hass, actions) == {
        "cover.xopen_garage",
        "light.xdeeper",
    }


async def test_a_parked_sequence_block_and_its_data_are_left_alone(
    hass: HomeAssistant,
) -> None:
    """A disabled block runs nothing, and a `sequence` in data is no step."""
    actions = [
        {"enabled": False, "sequence": [{"action": "cover.xparked_block"}]},
        {
            "sequence": [
                {"enabled": False, "action": "cover.xparked_step"},
                {
                    "action": "light.turn_on",
                    "data": {"sequence": [{"action": "cover.xjust_data"}]},
                },
            ]
        },
    ]

    assert await _unknown_in_automation(hass, actions) == set()
