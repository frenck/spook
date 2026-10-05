"""Tests for leaving disabled steps out of the automation entity repair."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def _unknown_in_automation(
    hass: HomeAssistant, config: dict[str, Any]
) -> set[str]:
    """Set up a real automation and ask the repair about it."""
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("binary_sensor.door", "off")
    assert await async_setup_component(
        hass,
        "automation",
        {"automation": {"id": "parked", "alias": "parked", **config}},
    )
    await hass.async_block_till_done()

    entity = hass.data["automation"].get_entity("automation.parked")
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(entity)


async def test_disabled_actions_triggers_and_conditions_are_left_out(
    hass: HomeAssistant,
) -> None:
    """Parked steps, triggers and conditions do nothing, so they report nothing.

    The noise discussion #1093 asks to be rid of.
    """
    config = {
        "triggers": [
            {"trigger": "state", "entity_id": "binary_sensor.door"},
            {
                "enabled": False,
                "trigger": "state",
                "entity_id": "binary_sensor.xparked_trigger",
            },
        ],
        "conditions": [
            {
                "enabled": False,
                "condition": "state",
                "entity_id": "binary_sensor.xparked_condition",
                "state": "on",
            }
        ],
        "actions": [
            {
                "enabled": False,
                "action": "light.turn_on",
                "target": {"entity_id": "light.xparked_action"},
            },
            {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
        ],
    }

    assert await _unknown_in_automation(hass, config) == set()


async def test_a_disabled_step_inside_a_branch_is_left_out(
    hass: HomeAssistant,
) -> None:
    """Parked is parked, however deep the step sits."""
    config = {
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.door"}],
        "actions": [
            {
                "if": [
                    {"condition": "state", "entity_id": "light.kitchen", "state": "on"}
                ],
                "then": [
                    {
                        "enabled": False,
                        "action": "light.turn_off",
                        "target": {"entity_id": "light.xdeep"},
                    }
                ],
            }
        ],
    }

    assert await _unknown_in_automation(hass, config) == set()


async def test_a_running_step_still_reports(hass: HomeAssistant) -> None:
    """Named by a step that runs as well, it can still break the automation."""
    config = {
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.door"}],
        "actions": [
            {
                "enabled": False,
                "action": "light.turn_on",
                "target": {"entity_id": "light.xbroken"},
            },
            {"action": "light.turn_off", "target": {"entity_id": "light.xbroken"}},
        ],
    }

    assert await _unknown_in_automation(hass, config) == {"light.xbroken"}
