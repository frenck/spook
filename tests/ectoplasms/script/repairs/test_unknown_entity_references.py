"""Golden-path tests for the script trigger-config extractor.

These tests pin down the synchronous, hass-free
``extract_entities_from_trigger_config`` helper in
``custom_components/spook/ectoplasms/script/repairs/unknown_entity_references.py``.
The function walks blueprint trigger inputs to harvest entity IDs; the rest of
the module needs a live ``hass`` and a populated script component, so it is
exercised by integration tests rather than module-level unit tests.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from custom_components.spook.ectoplasms.script.repairs.unknown_entity_references import (
    extract_entities_from_trigger_config,
)


def test_trigger_plain_entity_id() -> None:
    """A trigger dict with a string ``entity_id`` is captured."""
    config = {"platform": "state", "entity_id": "binary_sensor.door"}
    assert extract_entities_from_trigger_config(config) == {"binary_sensor.door"}


def test_trigger_entity_id_list() -> None:
    """A trigger dict with a list of entity IDs captures every string entry."""
    config = {"platform": "state", "entity_id": ["switch.lamp", "switch.fan", 42]}
    assert extract_entities_from_trigger_config(config) == {"switch.lamp", "switch.fan"}


def test_trigger_list_of_triggers_is_walked() -> None:
    """A top-level list of trigger configs is flattened."""
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
    """Nested dict values are walked recursively to find entity IDs."""
    config = {
        "platform": "state",
        "entity_id": "light.kitchen",
        "extra": {"entity_id": "switch.lamp"},
    }
    assert extract_entities_from_trigger_config(config) == {
        "light.kitchen",
        "switch.lamp",
    }


def test_trigger_empty_inputs_return_empty_set() -> None:
    """``None``, ``{}``, and ``[]`` all produce an empty set."""
    assert extract_entities_from_trigger_config(None) == set()  # type: ignore[arg-type]
    assert extract_entities_from_trigger_config({}) == set()
    assert extract_entities_from_trigger_config([]) == set()


def test_trigger_non_dict_non_list_returns_empty_set() -> None:
    """Strings, numbers, and other scalars short-circuit to an empty set."""
    assert extract_entities_from_trigger_config("not a config") == set()  # type: ignore[arg-type]
    assert extract_entities_from_trigger_config(42) == set()  # type: ignore[arg-type]


def test_trigger_without_entity_id_field() -> None:
    """A trigger config with no ``entity_id`` field yields nothing."""
    config = {"platform": "time", "at": "08:00:00"}
    assert extract_entities_from_trigger_config(config) == set()


def test_trigger_entity_id_with_non_string_in_list() -> None:
    """Non-string elements inside an entity_id list are silently dropped."""
    config = {"platform": "state", "entity_id": ["light.kitchen", None, 42]}
    assert extract_entities_from_trigger_config(config) == {"light.kitchen"}


def test_trigger_blueprint_input_shape() -> None:
    """A blueprint-style nested input dict is walked to find triggers."""
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
