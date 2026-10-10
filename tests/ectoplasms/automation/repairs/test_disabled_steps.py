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


async def test_what_only_core_reads_in_a_disabled_part_is_left_out(
    hass: HomeAssistant,
) -> None:
    """Home Assistant's own list reads keys Spook's walkers do not.

    The `at` of a time trigger, the `after` of a time condition, a scene step
    and a zone trigger waited for. Parked, none of them runs, whichever key
    core takes them from.
    """
    config = {
        "triggers": [
            {
                "enabled": False,
                "trigger": "time",
                "at": "input_datetime.xparked_at",
            },
            {"trigger": "state", "entity_id": "light.kitchen"},
        ],
        "conditions": [
            {
                "enabled": False,
                "condition": "time",
                "after": "input_datetime.xparked_after",
            }
        ],
        "actions": [
            {"enabled": False, "scene": "scene.xparked"},
            {
                "enabled": False,
                "wait_for_trigger": [
                    {
                        "trigger": "zone",
                        "entity_id": "person.xparked",
                        "zone": "zone.xparked",
                        "event": "enter",
                    }
                ],
            },
        ],
    }

    assert await _unknown_in_automation(hass, config) == set()


async def test_what_only_core_reads_in_a_nested_disabled_part_is_left_out(
    hass: HomeAssistant,
) -> None:
    """Parked is parked at any depth, for what only core reads as well.

    A step inside choose, if, parallel, repeat and a plain sequence, a
    condition inside and, or and not, and a trigger waited for in a list.
    """
    config = {
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.door"}],
        "conditions": [
            {
                "condition": "and",
                "conditions": [
                    {"condition": "state", "entity_id": "light.kitchen", "state": "on"},
                    {
                        "enabled": False,
                        "condition": "time",
                        "after": "input_datetime.xin_and",
                    },
                ],
            },
            {
                "condition": "or",
                "conditions": [
                    {"condition": "state", "entity_id": "light.kitchen", "state": "on"},
                    {
                        "enabled": False,
                        "condition": "time",
                        "before": "input_datetime.xin_or",
                    },
                ],
            },
            {
                "condition": "not",
                "conditions": [
                    {"condition": "state", "entity_id": "light.kitchen", "state": "on"},
                    {
                        "enabled": False,
                        "condition": "time",
                        "after": "input_datetime.xin_not",
                    },
                ],
            },
        ],
        "actions": [
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "enabled": False,
                                "condition": "time",
                                "after": "input_datetime.xin_choose",
                            }
                        ],
                        "sequence": [{"enabled": False, "scene": "scene.xin_choose"}],
                    }
                ],
                "default": [{"enabled": False, "scene": "scene.xin_default"}],
            },
            {
                "if": [
                    {"condition": "state", "entity_id": "light.kitchen", "state": "on"}
                ],
                "then": [{"enabled": False, "scene": "scene.xin_then"}],
                "else": [{"enabled": False, "scene": "scene.xin_else"}],
            },
            {"parallel": [{"enabled": False, "scene": "scene.xin_parallel"}]},
            {
                "repeat": {
                    "count": 2,
                    "sequence": [{"enabled": False, "scene": "scene.xin_repeat"}],
                }
            },
            {"sequence": [{"enabled": False, "scene": "scene.xin_sequence"}]},
            {
                "wait_for_trigger": [
                    {"trigger": "state", "entity_id": "light.kitchen"},
                    {
                        "enabled": False,
                        "trigger": "time",
                        "at": "input_datetime.xin_wait",
                    },
                ]
            },
        ],
    }

    assert await _unknown_in_automation(hass, config) == set()


async def test_a_templated_enabled_is_not_known_to_be_parked(
    hass: HomeAssistant,
) -> None:
    """A template decides at run time, so the step may well run.

    Home Assistant takes a template for `enabled`, and until it renders
    nobody knows. What such a part names is still reported.
    """
    config = {
        "triggers": [
            {
                "enabled": "{{ false }}",
                "trigger": "time",
                "at": "input_datetime.xmaybe_at",
            },
            {"trigger": "state", "entity_id": "binary_sensor.door"},
        ],
        "actions": [{"enabled": "{{ false }}", "scene": "scene.xmaybe"}],
    }

    assert await _unknown_in_automation(hass, config) == {
        "input_datetime.xmaybe_at",
        "scene.xmaybe",
    }


async def test_what_only_core_reads_is_still_reported_when_running_too(
    hass: HomeAssistant,
) -> None:
    """Parked in one place and running in another, it can still break things."""
    config = {
        "triggers": [
            {
                "enabled": False,
                "trigger": "time",
                "at": "input_datetime.xbroken_at",
            },
            {"trigger": "time", "at": "input_datetime.xbroken_at"},
        ],
        "actions": [
            {"enabled": False, "scene": "scene.xbroken"},
            {"sequence": [{"scene": "scene.xbroken"}]},
        ],
    }

    assert await _unknown_in_automation(hass, config) == {
        "input_datetime.xbroken_at",
        "scene.xbroken",
    }
