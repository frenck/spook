"""Golden-path tests for the automation entity-reference extractor.

These tests pin down the observable behavior of the module-level extractors used
by ``SpookRepair`` in
``custom_components/spook/ectoplasms/automation/repairs/unknown_entity_references.py``
so the upcoming consolidation into a single recursive walker cannot regress them
silently.
"""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    extract_entities_from_action_config,
    extract_entities_from_automation_config,
    extract_entities_from_condition_config,
    extract_entities_from_trigger_config,
    extract_entities_from_value,
)
import pytest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ---------------------------------------------------------------------------
# extract_entities_from_value
# ---------------------------------------------------------------------------


async def test_value_plain_entity_id(hass: HomeAssistant) -> None:
    """A bare entity ID string is recognized as an entity reference."""
    assert await extract_entities_from_value(hass, "light.kitchen") == {"light.kitchen"}


async def test_value_unknown_domain_is_ignored(hass: HomeAssistant) -> None:
    """Strings using an unknown domain are not treated as entity IDs."""
    assert await extract_entities_from_value(hass, "totally_made_up.kitchen") == set()


async def test_value_list_of_entity_ids(hass: HomeAssistant) -> None:
    """A list of entity ID strings yields every valid entry."""
    result = await extract_entities_from_value(
        hass, ["light.kitchen", "switch.lamp", "not_a_domain.foo"]
    )
    assert result == {"light.kitchen", "switch.lamp"}


async def test_value_entity_dict_form(hass: HomeAssistant) -> None:
    """``{"entity": "..."}`` dicts are unwrapped into their entity ID."""
    assert await extract_entities_from_value(
        hass, {"entity": "sensor.temperature"}
    ) == {"sensor.temperature"}


async def test_value_template_extracts_referenced_entity(
    hass: HomeAssistant,
) -> None:
    """Template strings have their referenced entity IDs extracted."""
    template = "{{ states('light.kitchen') }}"
    assert await extract_entities_from_value(hass, template) == {"light.kitchen"}


async def test_value_non_string_non_collection_returns_empty(
    hass: HomeAssistant,
) -> None:
    """Numbers, booleans, and None yield no entities."""
    assert await extract_entities_from_value(hass, 42) == set()
    assert await extract_entities_from_value(hass, None) == set()
    assert await extract_entities_from_value(hass, True) == set()


# ---------------------------------------------------------------------------
# extract_entities_from_trigger_config
# ---------------------------------------------------------------------------


async def test_trigger_state_entity_id(hass: HomeAssistant) -> None:
    """A state trigger's ``entity_id`` is captured."""
    config = {"platform": "state", "entity_id": "binary_sensor.door"}
    assert await extract_entities_from_trigger_config(hass, config) == {
        "binary_sensor.door"
    }


async def test_trigger_zone_field(hass: HomeAssistant) -> None:
    """A zone trigger's ``zone`` field is captured."""
    config = {
        "platform": "zone",
        "entity_id": "person.alice",
        "zone": "zone.home",
        "event": "enter",
    }
    assert await extract_entities_from_trigger_config(hass, config) == {
        "person.alice",
        "zone.home",
    }


async def test_trigger_list_of_triggers(hass: HomeAssistant) -> None:
    """Lists of triggers are walked recursively."""
    config = [
        {"platform": "state", "entity_id": "light.kitchen"},
        {"platform": "state", "entity_id": ["switch.lamp", "switch.fan"]},
    ]
    assert await extract_entities_from_trigger_config(hass, config) == {
        "light.kitchen",
        "switch.lamp",
        "switch.fan",
    }


async def test_trigger_empty_or_none_returns_empty(hass: HomeAssistant) -> None:
    """Empty inputs produce no entities."""
    assert await extract_entities_from_trigger_config(hass, None) == set()
    assert await extract_entities_from_trigger_config(hass, {}) == set()
    assert await extract_entities_from_trigger_config(hass, []) == set()


# ---------------------------------------------------------------------------
# extract_entities_from_condition_config
# ---------------------------------------------------------------------------


async def test_condition_state_entity_id(hass: HomeAssistant) -> None:
    """A state condition's ``entity_id`` is captured."""
    config = {"condition": "state", "entity_id": "switch.lamp", "state": "on"}
    assert await extract_entities_from_condition_config(hass, config) == {"switch.lamp"}


async def test_condition_zone(hass: HomeAssistant) -> None:
    """Zone conditions capture both the tracked entity and the zone."""
    config = {
        "condition": "zone",
        "entity_id": "person.alice",
        "zone": "zone.home",
    }
    assert await extract_entities_from_condition_config(hass, config) == {
        "person.alice",
        "zone.home",
    }


async def test_condition_nested_and(hass: HomeAssistant) -> None:
    """An ``and`` condition recurses into its nested condition list."""
    config = {
        "condition": "and",
        "conditions": [
            {"condition": "state", "entity_id": "light.kitchen", "state": "on"},
            {"condition": "numeric_state", "entity_id": "sensor.temperature"},
        ],
    }
    assert await extract_entities_from_condition_config(hass, config) == {
        "light.kitchen",
        "sensor.temperature",
    }


# ---------------------------------------------------------------------------
# extract_entities_from_action_config
# ---------------------------------------------------------------------------


async def test_action_direct_entity_id(hass: HomeAssistant) -> None:
    """A direct ``entity_id`` on an action is captured."""
    config = {"service": "light.turn_on", "entity_id": "light.kitchen"}
    assert await extract_entities_from_action_config(hass, config) == {"light.kitchen"}


async def test_action_target_block(hass: HomeAssistant) -> None:
    """``target.entity_id`` on an action is captured."""
    config = {
        "service": "light.turn_on",
        "target": {"entity_id": ["light.kitchen", "light.living_room"]},
    }
    assert await extract_entities_from_action_config(hass, config) == {
        "light.kitchen",
        "light.living_room",
    }


async def test_action_data_dict(hass: HomeAssistant) -> None:
    """Entities buried inside ``data`` values are captured."""
    config = {
        "service": "notify.notify",
        "data": {"message": "hello", "target": "person.alice"},
    }
    assert await extract_entities_from_action_config(hass, config) == {"person.alice"}


async def test_action_data_as_template_string(hass: HomeAssistant) -> None:
    """A template string assigned directly to ``data`` is parsed."""
    config = {
        "service": "notify.notify",
        "data": "{{ states('sensor.temperature') }}",
    }
    assert await extract_entities_from_action_config(hass, config) == {
        "sensor.temperature"
    }


async def test_action_if_then_else_nested(hass: HomeAssistant) -> None:
    """``if``/``then``/``else`` nested actions are walked."""
    config = {
        "if": [{"condition": "state", "entity_id": "binary_sensor.door"}],
        "then": [{"service": "light.turn_on", "target": {"entity_id": "light.hall"}}],
        "else": [{"service": "light.turn_off", "target": {"entity_id": "light.hall"}}],
    }
    result = await extract_entities_from_action_config(hass, config)
    assert {"binary_sensor.door", "light.hall"} <= result


async def test_action_list_of_actions(hass: HomeAssistant) -> None:
    """A top-level list of actions is walked."""
    config = [
        {"service": "light.turn_on", "target": {"entity_id": "light.a"}},
        {"service": "switch.turn_on", "entity_id": "switch.b"},
    ]
    assert await extract_entities_from_action_config(hass, config) == {
        "light.a",
        "switch.b",
    }


# ---------------------------------------------------------------------------
# extract_entities_from_automation_config (orchestrator)
# ---------------------------------------------------------------------------


async def test_automation_full_config(hass: HomeAssistant) -> None:
    """A complete automation config yields entities from all three sections."""
    config = {
        "alias": "Test",
        "trigger": [{"platform": "state", "entity_id": "binary_sensor.motion"}],
        "condition": [
            {"condition": "state", "entity_id": "input_boolean.guest", "state": "on"}
        ],
        "action": [
            {"service": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
        ],
    }
    assert await extract_entities_from_automation_config(hass, config) == {
        "binary_sensor.motion",
        "input_boolean.guest",
        "light.kitchen",
    }


async def test_automation_non_dict_returns_empty(hass: HomeAssistant) -> None:
    """A non-dict argument short-circuits to an empty set."""
    assert await extract_entities_from_automation_config(hass, []) == set()
    assert await extract_entities_from_automation_config(hass, "not a dict") == set()


@pytest.mark.parametrize("section", ["trigger", "condition", "action"])
async def test_automation_missing_sections(hass: HomeAssistant, section: str) -> None:
    """Automations missing one of the three sections still extract from the rest."""
    config = {
        "trigger": [{"platform": "state", "entity_id": "binary_sensor.t"}],
        "condition": [
            {"condition": "state", "entity_id": "binary_sensor.c", "state": "on"}
        ],
        "action": [{"service": "light.turn_on", "entity_id": "light.a"}],
    }
    config.pop(section)
    result = await extract_entities_from_automation_config(hass, config)
    expected = {
        "trigger": {"binary_sensor.c", "light.a"},
        "condition": {"binary_sensor.t", "light.a"},
        "action": {"binary_sensor.t", "binary_sensor.c"},
    }[section]
    assert result == expected
