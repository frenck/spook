"""Tests for script unknown entity reference helpers."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.script.repairs.unknown_entity_references import (
    SpookRepair,
    extract_referenced_entities_from_script,
)

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant


class MockScript:  # pylint: disable=too-few-public-methods
    """Mock script object."""

    def __init__(self, referenced_entities: set[str]) -> None:
        """Initialize the mock script."""
        self.referenced_entities = referenced_entities


class MockBrokenScript:  # pylint: disable=too-few-public-methods
    """Mock script object with broken referenced entity extraction."""

    @property
    def referenced_entities(self) -> set[str]:
        """Raise the same error Home Assistant can raise for dict entity IDs."""
        msg = "unhashable type: 'dict'"
        raise TypeError(msg)


class MockUnexpectedBrokenScript:  # pylint: disable=too-few-public-methods
    """Mock script object with an unrelated TypeError."""

    @property
    def referenced_entities(self) -> set[str]:
        """Raise an unexpected TypeError."""
        msg = "unexpected failure"
        raise TypeError(msg)


class MockScriptEntity:  # pylint: disable=too-few-public-methods
    """Mock script entity."""

    def __init__(
        self, script: MockScript | MockBrokenScript | MockUnexpectedBrokenScript
    ) -> None:
        """Initialize the mock script entity."""
        self.script = script


def test_extract_referenced_entities_from_script() -> None:
    """Test script referenced entities are returned as a set."""
    entity = MockScriptEntity(MockScript({"light.kitchen"}))

    assert extract_referenced_entities_from_script(entity) == {"light.kitchen"}


def test_extract_referenced_entities_handles_home_assistant_type_error() -> None:
    """Test broken Home Assistant referenced entity extraction is ignored."""
    entity = MockScriptEntity(MockBrokenScript())

    assert extract_referenced_entities_from_script(entity) == set()


def test_extract_referenced_entities_reraises_unexpected_type_error() -> None:
    """Test unrelated TypeErrors are not swallowed."""
    entity = MockScriptEntity(MockUnexpectedBrokenScript())

    with pytest.raises(TypeError, match="unexpected failure"):
        extract_referenced_entities_from_script(entity)


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
