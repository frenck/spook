"""Tests for script unknown entity reference helpers."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.script.repairs.unknown_entity_references import (
    SpookRepair,
)
from custom_components.spook.reference_extraction import core_references

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant


async def _unknown_in_script(
    hass: HomeAssistant, scripts: dict[str, Any], script_id: str
) -> set[str]:
    """Set up real scripts and ask the repair about one of them."""
    hass.states.async_set("light.fireplace_pots", "on")
    hass.states.async_set("light.kitchen_counter_pendants", "on")
    assert await async_setup_component(hass, "script", {"script": scripts})
    await hass.async_block_till_done()

    entity = hass.data["script"].get_entity(f"script.{script_id}")
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(entity)


# The receiving end of the call in discussion #1722. Its fields are left out:
# what matters is the calling side, and what it hands over.
_RECEIVER = {"sequence": [{"variables": {"devices": "{{ list_of_devices }}"}}]}


async def test_entities_handed_to_another_script_are_checked(
    hass: HomeAssistant,
) -> None:
    """A typo in data handed to another script is reported.

    Home Assistant's own list of what a script references leaves action data
    out. The automation repair read it already, the script repair did not, so
    a script calling a script got away with it.
    """
    scripts = {
        "event_creator": _RECEIVER,
        "evening": {
            "sequence": [
                {
                    "action": "script.event_creator",
                    "data": {
                        "list_of_devices": [
                            {"entity": "light.xkitchen_counter_pendants"},
                            {"entity": "light.fireplace_pots"},
                        ]
                    },
                }
            ]
        },
    }

    assert await _unknown_in_script(hass, scripts, "evening") == {
        "light.xkitchen_counter_pendants"
    }


async def test_templates_in_a_script_are_checked(hass: HomeAssistant) -> None:
    """An unknown entity in a template outside the steps is reported.

    Templates in the steps are read along with the action data. One in the
    script's own variables only the template scan sees, and that scan read a
    configuration the script helper underneath never had, so it never found
    anything.
    """
    scripts = {
        "evening": {
            "variables": {
                "level": "{{ state_attr('light.xfireplace', 'brightness') }}"
            },
            "sequence": [
                {
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.fireplace_pots"},
                    "data": {"brightness": "{{ level }}"},
                }
            ],
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == {"light.xfireplace"}


async def test_a_script_with_only_known_entities_is_clean(hass: HomeAssistant) -> None:
    """Nothing to report when everything handed over exists."""
    scripts = {
        "event_creator": _RECEIVER,
        "evening": {
            "sequence": [
                {
                    "action": "script.event_creator",
                    "data": {
                        "list_of_devices": [
                            {"entity": "light.kitchen_counter_pendants"},
                            {"entity": "light.fireplace_pots"},
                        ]
                    },
                }
            ]
        },
    }

    assert await _unknown_in_script(hass, scripts, "evening") == set()


async def test_an_entity_only_a_disabled_step_names_is_left_out(
    hass: HomeAssistant,
) -> None:
    """A disabled step does nothing, so what only it names is not a problem.

    People disable a step on purpose, to park it. Reporting what it names is
    the noise discussion #1093 asks to be rid of.
    """
    scripts = {
        "evening": {
            "sequence": [
                {
                    "enabled": False,
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.xparked"},
                    "data": {
                        "brightness": "{{ state_attr('light.xtemplated', 'level') }}"
                    },
                },
                {
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.fireplace_pots"},
                },
            ]
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == set()


async def test_an_entity_a_running_step_names_too_is_still_reported(
    hass: HomeAssistant,
) -> None:
    """Named by a step that runs as well, it can still break the script."""
    scripts = {
        "evening": {
            "sequence": [
                {
                    "enabled": False,
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.xbroken"},
                },
                {"action": "light.turn_off", "target": {"entity_id": "light.xbroken"}},
            ]
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == {"light.xbroken"}


async def test_a_running_variable_still_reports_what_a_parked_step_names(
    hass: HomeAssistant,
) -> None:
    """The script's own variables run regardless of any parked step."""
    scripts = {
        "evening": {
            "variables": {"level": "{{ state_attr('light.xbroken', 'brightness') }}"},
            "sequence": [
                {
                    "enabled": False,
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.xbroken"},
                },
                {
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.fireplace_pots"},
                },
            ],
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == {"light.xbroken"}


async def test_what_only_core_reads_in_a_disabled_step_is_left_out(
    hass: HomeAssistant,
) -> None:
    """Home Assistant's own list reads keys Spook's walkers do not.

    A scene step, a time condition and a zone trigger waited for. Parked,
    none of them runs, whichever key core takes them from.
    """
    scripts = {
        "evening": {
            "sequence": [
                {"enabled": False, "scene": "scene.xparked"},
                {
                    "enabled": False,
                    "condition": "time",
                    "after": "input_datetime.xparked_after",
                },
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
            ]
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == set()


async def test_what_only_core_reads_in_a_nested_disabled_part_is_left_out(
    hass: HomeAssistant,
) -> None:
    """Parked is parked at any depth, for what only core reads as well."""
    running = {"condition": "state", "entity_id": "light.fireplace_pots", "state": "on"}
    scripts = {
        "evening": {
            "sequence": [
                {
                    "choose": [
                        {
                            "conditions": [
                                {
                                    "condition": "and",
                                    "conditions": [
                                        running,
                                        {
                                            "enabled": False,
                                            "condition": "time",
                                            "after": "input_datetime.xin_and",
                                        },
                                    ],
                                }
                            ],
                            "sequence": [
                                {"enabled": False, "scene": "scene.xin_choose"}
                            ],
                        }
                    ],
                    "default": [{"enabled": False, "scene": "scene.xin_default"}],
                },
                {
                    "if": [
                        {
                            "condition": "not",
                            "conditions": [
                                running,
                                {
                                    "enabled": False,
                                    "condition": "zone",
                                    "entity_id": "person.xin_not",
                                    "zone": "zone.xin_not",
                                },
                            ],
                        }
                    ],
                    "then": [{"enabled": False, "scene": "scene.xin_then"}],
                },
                {"parallel": [{"enabled": False, "scene": "scene.xin_parallel"}]},
                {
                    "repeat": {
                        "while": [
                            {
                                "condition": "or",
                                "conditions": [
                                    running,
                                    {
                                        "enabled": False,
                                        "condition": "time",
                                        "before": "input_datetime.xin_or",
                                    },
                                ],
                            }
                        ],
                        "sequence": [{"enabled": False, "scene": "scene.xin_repeat"}],
                    }
                },
                {
                    "wait_for_trigger": [
                        {"trigger": "state", "entity_id": "light.fireplace_pots"},
                        {
                            "enabled": False,
                            "trigger": "time",
                            "at": "input_datetime.xin_wait",
                        },
                    ]
                },
            ]
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == set()


async def test_a_step_with_a_templated_enabled_still_reports(
    hass: HomeAssistant,
) -> None:
    """A template decides at run time, so the step may well run."""
    scripts = {
        "evening": {
            "sequence": [{"enabled": "{{ false }}", "scene": "scene.xmaybe"}],
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == {"scene.xmaybe"}


async def test_what_only_core_reads_is_still_reported_when_running_too(
    hass: HomeAssistant,
) -> None:
    """Parked in one place and running in another, it can still break things."""
    scripts = {
        "evening": {
            "sequence": [
                {"enabled": False, "scene": "scene.xbroken"},
                {"sequence": [{"scene": "scene.xbroken"}]},
            ],
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == {"scene.xbroken"}


async def test_a_blueprint_script_is_read_as_filled_in(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """A script on a blueprint is read with its inputs filled in.

    Home Assistant keeps the filled-in configuration as the script's own, so
    an unknown entity handed over as input is found in its steps, like any
    other.
    """
    hass.config.config_dir = str(tmp_path)
    blueprint = tmp_path / "blueprints" / "script" / "frenck" / "parked.yaml"
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text(
        """
blueprint:
  name: Parked
  domain: script
  input:
    lamp:
      selector:
        entity:
sequence:
  - action: light.turn_on
    target:
      entity_id: !input lamp
""",
        encoding="utf-8",
    )

    scripts = {
        "evening": {
            "use_blueprint": {
                "path": "frenck/parked.yaml",
                "input": {"lamp": "light.xgone"},
            }
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == {"light.xgone"}


async def test_a_template_in_a_disabled_step_is_left_out(hass: HomeAssistant) -> None:
    """A parked `wait_template` is parked too, like any other part of the step."""
    scripts = {
        "evening": {
            "sequence": [
                {
                    "enabled": False,
                    "wait_template": "{{ is_state('light.xmissing', 'on') }}",
                },
                {
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.fireplace_pots"},
                },
            ]
        }
    }

    assert await _unknown_in_script(hass, scripts, "evening") == set()


def _waiting_for(event_type: str, *steps: dict[str, Any]) -> dict[str, Any]:
    """Return a script waiting for an event carrying `light.from_the_remote`."""
    wait = {
        "wait_for_trigger": [
            {
                "trigger": "event",
                "event_type": event_type,
                "event_data": {"entity_id": "light.from_the_remote"},
            }
        ]
    }
    return {"sequence": [wait, *steps]}


async def test_a_custom_event_payload_is_no_unknown_entity(
    hass: HomeAssistant,
) -> None:
    """Test the entity in somebody's own event waited for is not reported.

    Home Assistant's own list takes it from any event trigger, also one
    waited for in a step: that is the premise, so it is checked here too.
    """
    assert await async_setup_component(
        hass, "script", {"script": {"remote": _waiting_for("my_remote_pressed")}}
    )
    await hass.async_block_till_done()
    entity = hass.data["script"].get_entity("script.remote")
    assert "light.from_the_remote" in core_references(entity, "entities")

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_a_custom_event_payload_named_elsewhere_still_counts(
    hass: HomeAssistant,
) -> None:
    """Test an entity in the payload that is also used for real is reported."""
    scripts = {
        "remote": _waiting_for(
            "my_remote_pressed",
            {
                "action": "light.turn_on",
                "target": {"entity_id": "light.from_the_remote"},
            },
        )
    }

    assert await _unknown_in_script(hass, scripts, "remote") == {
        "light.from_the_remote"
    }


async def test_an_integration_event_payload_is_still_reported(
    hass: HomeAssistant,
) -> None:
    """Test the entity in an integration's own event still is a reference."""
    scripts = {"remote": _waiting_for("timer.finished")}

    assert await _unknown_in_script(hass, scripts, "remote") == {
        "light.from_the_remote"
    }


async def test_event_fields_in_action_data_are_still_read(
    hass: HomeAssistant,
) -> None:
    """Test action data shaped like an event trigger is no event trigger.

    It is whatever the called action takes, so an entity in there is read
    like any other in action data.
    """
    scripts = {
        "relay": {
            "sequence": [
                {
                    "action": "script.forward",
                    "data": {
                        "trigger": "event",
                        "event_type": "my_remote_pressed",
                        "event_data": {"entity_id": "light.from_the_remote"},
                    },
                }
            ]
        },
        "forward": {"sequence": []},
    }

    assert await _unknown_in_script(hass, scripts, "relay") == {"light.from_the_remote"}


async def test_a_custom_event_payload_only_core_also_reads_still_counts(
    hass: HomeAssistant,
) -> None:
    """Test an entity also activated with the scene shorthand is reported.

    Only Home Assistant's own reading sees the `scene:` step, so the entity
    being named somewhere else in the configuration is what keeps it in.
    """
    scripts = {"remote": _waiting_for("my_remote_pressed", {"scene": "scene.movie"})}
    scripts["remote"]["sequence"][0]["wait_for_trigger"][0]["event_data"] = {
        "entity_id": "scene.movie"
    }

    assert await _unknown_in_script(hass, scripts, "remote") == {"scene.movie"}


async def test_event_fields_in_old_style_action_data_are_still_read(
    hass: HomeAssistant,
) -> None:
    """Test `data_template` is action data too, never an event trigger."""
    scripts = {
        "relay": {
            "sequence": [
                {
                    "action": "script.forward",
                    "data_template": {
                        "trigger": "event",
                        "event_type": "my_remote_pressed",
                        "event_data": {"entity_id": "light.from_the_remote"},
                    },
                }
            ]
        },
        "forward": {"sequence": []},
    }

    assert await _unknown_in_script(hass, scripts, "relay") == {"light.from_the_remote"}


async def test_a_field_example_names_no_entity(hass: HomeAssistant) -> None:
    """Test an example template in a field or a step name is not read.

    Home Assistant shows those, it never renders them.
    """
    scripts = {
        "announce": {
            "fields": {
                "message": {
                    "example": "{{ states('sensor.field_example_ghost') }}",
                    "selector": {"text": {}},
                }
            },
            "sequence": [
                {
                    "alias": "Was {{ states('sensor.step_name_example') }}",
                    "delay": 1,
                }
            ],
        }
    }

    assert await _unknown_in_script(hass, scripts, "announce") == set()


async def test_repeat_items_are_rendered_whatever_their_keys(
    hass: HomeAssistant,
) -> None:
    """Test the items a repeat goes over are read, also a `description` there.

    Home Assistant renders each item as a whole, so it is no name or
    description of the script, whatever its keys are called.
    """
    scripts = {
        "rounds": {
            "sequence": [
                {
                    "repeat": {
                        "for_each": [
                            {"description": "{{ states('sensor.repeat_ghost') }}"}
                        ],
                        "sequence": [{"delay": 0}],
                    }
                }
            ]
        }
    }

    assert await _unknown_in_script(hass, scripts, "rounds") == {"sensor.repeat_ghost"}


async def test_a_state_change_waited_for_is_still_reported(
    hass: HomeAssistant,
) -> None:
    """Test the entity of a `state_changed` event waited for is a reference."""
    scripts = {"remote": _waiting_for("state_changed")}

    assert await _unknown_in_script(hass, scripts, "remote") == {
        "light.from_the_remote"
    }


async def test_a_missing_numeric_state_threshold_entity_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test the entity a condition in a step compares against is a reference.

    Home Assistant reads the threshold from that entity, so with it gone the
    condition fails. A trigger waited for reads it the same way, and a plain
    number is no entity at all.
    """
    hass.states.async_set("sensor.freezer_temperature", "-18")
    scripts = {
        "freezer": {
            "sequence": [
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.freezer_temperature",
                    "below": "input_number.freezer_limit",
                    "above": -30,
                },
                {
                    "wait_for_trigger": [
                        {
                            "trigger": "numeric_state",
                            "entity_id": "sensor.freezer_temperature",
                            "above": "number.freezer_alarm",
                        }
                    ]
                },
            ]
        }
    }

    assert await _unknown_in_script(hass, scripts, "freezer") == {
        "input_number.freezer_limit",
        "number.freezer_alarm",
    }


def _brightness(kind: str, value: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Return a light brightness trigger or condition comparing against ``value``."""
    return {
        kind: (
            "light.is_brightness"
            if kind == "condition"
            else "light.brightness_crossed_threshold"
        ),
        "target": {"entity_id": "light.kitchen"},
        "options": {"threshold": {"type": "above", "value": value}},
        **extra,
    }


async def test_a_missing_threshold_entity_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test the entity a new style threshold in a step compares against is read.

    A condition step and a trigger waited for read it the same way. Only the
    choice `active_choice` points at counts, and a parked step does nothing.
    """
    hass.states.async_set("light.kitchen", "on")
    percent = {"number": 50, "unit_of_measurement": "%"}
    scripts = {
        "brightness": {
            "sequence": [
                _brightness("condition", {"entity": "input_number.condition_limit"}),
                {
                    "wait_for_trigger": [
                        _brightness(
                            "trigger",
                            {
                                "active_choice": "entity",
                                "entity": "input_number.waited_limit",
                                **percent,
                            },
                        )
                    ]
                },
                _brightness(
                    "condition",
                    {
                        "active_choice": "number",
                        "entity": "input_number.not_chosen",
                        **percent,
                    },
                ),
                _brightness(
                    "condition",
                    {"entity": "input_number.parked_limit"},
                    enabled=False,
                ),
            ]
        }
    }

    assert await _unknown_in_script(hass, scripts, "brightness") == {
        "input_number.condition_limit",
        "input_number.waited_limit",
    }


def _logging(entity_id: str, *steps: dict[str, Any]) -> dict[str, Any]:
    """Return a script filing a logbook entry under ``entity_id``."""
    log = {
        "action": "logbook.log",
        "data": {"entity_id": entity_id, "name": "Alert", "message": "Water"},
    }
    return {"sequence": [log, *steps]}


async def test_a_made_up_entity_to_file_a_logbook_entry_under_is_fine(
    hass: HomeAssistant,
) -> None:
    """Test `logbook.log` under an ID no integration provides is not reported.

    Home Assistant's own list takes it: that is the premise, so it is checked
    here too.
    """
    assert await async_setup_component(
        hass, "script", {"script": {"alert": _logging("log.critical_messages")}}
    )
    await hass.async_block_till_done()
    entity = hass.data["script"].get_entity("script.alert")
    assert "log.critical_messages" in core_references(entity, "entities")

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_a_removed_entity_to_file_a_logbook_entry_under_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test `logbook.log` under a real domain still checks the entity."""
    scripts = {"alert": _logging("light.gone")}

    assert await _unknown_in_script(hass, scripts, "alert") == {"light.gone"}


async def test_a_made_up_logbook_entity_also_used_as_a_target_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test the same made-up ID used as a target too is still reported."""
    scripts = {
        "alert": _logging(
            "log.critical_messages",
            {
                "action": "homeassistant.turn_on",
                "target": {"entity_id": "log.critical_messages"},
            },
        )
    }

    assert await _unknown_in_script(hass, scripts, "alert") == {"log.critical_messages"}


async def test_an_event_waited_for_and_a_logbook_entry_do_not_cancel_out(
    hass: HomeAssistant,
) -> None:
    """Test a waited for event payload and a logbook entry of one ID stay fine."""
    script = _logging("light.from_the_remote")
    script["sequence"] = [
        _waiting_for("my_remote_pressed")["sequence"][0],
        {
            "action": "logbook.log",
            "data": {"entity_id": "log.remote", "name": "x", "message": "y"},
        },
    ]
    script["sequence"][0]["wait_for_trigger"][0]["event_data"] = {
        "entity_id": "log.remote"
    }

    assert await _unknown_in_script(hass, {"remote": script}, "remote") == set()
