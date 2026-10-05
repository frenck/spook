"""Tests for script unknown entity reference helpers."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.script.repairs.unknown_entity_references import (
    SpookRepair,
    extract_entities_from_trigger_config,
    extract_referenced_entities_from_script,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def test_trigger_plain_entity_id() -> None:
    """Test a trigger with a string entity ID is captured."""
    config = {"platform": "state", "entity_id": "binary_sensor.door"}

    assert extract_entities_from_trigger_config(config) == {"binary_sensor.door"}


def test_trigger_entity_id_list() -> None:
    """Test a trigger with a list of entity IDs captures every string entry."""
    config = {"platform": "state", "entity_id": ["switch.lamp", "switch.fan", 42]}

    assert extract_entities_from_trigger_config(config) == {"switch.lamp", "switch.fan"}


def test_trigger_list_of_triggers_is_walked() -> None:
    """Test a top-level list of trigger configs is flattened."""
    config = [
        {"platform": "state", "entity_id": "light.kitchen"},
        {"platform": "state", "entity_id": ["switch.a", "switch.b"]},
    ]

    assert extract_entities_from_trigger_config(config) == {
        "light.kitchen",
        "switch.a",
        "switch.b",
    }


def test_trigger_nested_dict_is_walked() -> None:
    """Test nested dict values are walked recursively to find entity IDs."""
    config = {
        "platform": "state",
        "entity_id": "light.kitchen",
        "extra": {"entity_id": "switch.lamp"},
    }

    assert extract_entities_from_trigger_config(config) == {
        "light.kitchen",
        "switch.lamp",
    }


@pytest.mark.parametrize("config", [None, {}, []])
def test_trigger_empty_inputs_return_empty_set(config: Any) -> None:
    """Test empty trigger inputs produce an empty set."""
    assert extract_entities_from_trigger_config(config) == set()


@pytest.mark.parametrize("config", ["not a config", 42])
def test_trigger_non_dict_non_list_returns_empty_set(config: Any) -> None:
    """Test scalar trigger inputs produce an empty set."""
    assert extract_entities_from_trigger_config(config) == set()


def test_trigger_without_entity_id_field() -> None:
    """Test a trigger config with no entity ID field yields nothing."""
    config = {"platform": "time", "at": "08:00:00"}

    assert extract_entities_from_trigger_config(config) == set()


def test_trigger_entity_id_with_non_string_in_list() -> None:
    """Test non-string elements inside an entity ID list are ignored."""
    config = {"platform": "state", "entity_id": ["light.kitchen", None, 42]}

    assert extract_entities_from_trigger_config(config) == {"light.kitchen"}


def test_trigger_blueprint_input_shape() -> None:
    """Test a blueprint-style nested input dict is walked to find triggers."""
    config = {
        "discard_when": {
            "trigger": [
                {"platform": "state", "entity_id": "binary_sensor.motion"},
                {"platform": "state", "entity_id": ["light.a", "light.b"]},
            ],
        },
    }

    assert extract_entities_from_trigger_config(config) == {
        "binary_sensor.motion",
        "light.a",
        "light.b",
    }


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
