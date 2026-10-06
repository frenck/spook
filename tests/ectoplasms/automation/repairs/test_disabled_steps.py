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


async def test_a_single_disabled_step_without_a_list_is_left_out(
    hass: HomeAssistant,
) -> None:
    """One step written as a mapping rather than a list is parked all the same."""
    config = {
        "triggers": {"trigger": "state", "entity_id": "binary_sensor.door"},
        "actions": {
            "enabled": False,
            "action": "light.turn_on",
            "target": {"entity_id": "light.xparked"},
        },
    }

    assert await _unknown_in_automation(hass, config) == set()


async def test_a_running_template_outside_the_steps_still_reports(
    hass: HomeAssistant,
) -> None:
    """An automation's own variables run regardless of any parked step.

    An entity a disabled step names and a template in those variables names
    too is still in use, so it is still reported.
    """
    config = {
        "variables": {"level": "{{ state_attr('light.xbroken', 'brightness') }}"},
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.door"}],
        "actions": [
            {
                "enabled": False,
                "action": "light.turn_on",
                "target": {"entity_id": "light.xbroken"},
            },
            {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
        ],
    }

    assert await _unknown_in_automation(hass, config) == {"light.xbroken"}


async def test_a_disabled_template_condition_is_left_out(hass: HomeAssistant) -> None:
    """Templates in a parked condition are parked too.

    The report reads templates as well as structure, so what is left out has
    to be read the same way.
    """
    config = {
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.door"}],
        "conditions": [
            {
                "enabled": False,
                "condition": "template",
                "value_template": "{{ is_state('light.xparked', 'on') }}",
            }
        ],
        "actions": [
            {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}}
        ],
    }

    assert await _unknown_in_automation(hass, config) == set()


async def test_a_running_template_condition_still_reports(hass: HomeAssistant) -> None:
    """Named by a running template condition and a parked step, it is in use."""
    config = {
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.door"}],
        "conditions": [
            {
                "condition": "template",
                "value_template": "{{ is_state('light.xbroken', 'on') }}",
            }
        ],
        "actions": [
            {
                "enabled": False,
                "action": "light.turn_on",
                "target": {"entity_id": "light.xbroken"},
            },
            {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
        ],
    }

    assert await _unknown_in_automation(hass, config) == {"light.xbroken"}


async def test_a_running_zone_condition_still_reports(hass: HomeAssistant) -> None:
    """A zone a running condition names is in use, whatever a parked step says."""
    hass.states.async_set("person.anne", "home")
    config = {
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.door"}],
        "conditions": [
            {"condition": "zone", "entity_id": "person.anne", "zone": "zone.xgone"}
        ],
        "actions": [
            {
                "enabled": False,
                "action": "zone.update",
                "target": {"entity_id": "zone.xgone"},
            },
            {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
        ],
    }

    assert await _unknown_in_automation(hass, config) == {"zone.xgone"}
