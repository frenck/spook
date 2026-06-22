"""Tests for script unknown entity reference helpers."""

from __future__ import annotations

from typing import Any

import pytest

from custom_components.spook.ectoplasms.script.repairs.unknown_entity_references import (
    extract_entities_from_trigger_config,
    extract_referenced_entities_from_script,
)


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
