"""Golden-path tests for the automation entity-reference extractor.

These tests pin down the observable behavior of the module-level extractors used
by ``SpookRepair`` in
``custom_components/spook/ectoplasms/automation/repairs/unknown_entity_references.py``
so the upcoming consolidation into a single recursive walker cannot regress them
silently.
"""

# ruff: noqa: SLF001
# pylint: disable=protected-access,too-few-public-methods,wrong-import-order
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import ServiceRegistry, State
from homeassistant.setup import async_setup_component

from custom_components.spook.action_extraction import (
    async_extract_entities_from_action_config,
    async_extract_entities_from_value,
)
from custom_components.spook.entity_filtering import async_get_all_services
from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    SpookRepair,
    extract_entities_from_automation_config,
    extract_entities_from_condition_config,
    extract_entities_from_trigger_config,
)
import pytest

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from homeassistant.core import HomeAssistant


class MockAutomationEntity:
    """Mock automation entity."""

    def __init__(
        self,
        *,
        raw_config: dict[str, object],
        referenced_entities: Iterable[str],
    ) -> None:
        """Initialize the mock automation entity."""
        self.raw_config = raw_config
        self.referenced_entities = set(referenced_entities)


async def test_value_plain_entity_id(hass: HomeAssistant) -> None:
    """A bare entity ID string is recognized as an entity reference."""
    assert await async_extract_entities_from_value(hass, "light.kitchen") == {
        "light.kitchen"
    }


async def test_value_unknown_domain_is_ignored(hass: HomeAssistant) -> None:
    """Strings using an unknown domain are not treated as entity IDs."""
    assert (
        await async_extract_entities_from_value(hass, "totally_made_up.kitchen")
        == set()
    )


async def test_value_list_of_entity_ids(hass: HomeAssistant) -> None:
    """A list of entity ID strings yields every valid entry."""
    result = await async_extract_entities_from_value(
        hass, ["light.kitchen", "switch.lamp", "not_a_domain.foo"]
    )
    assert result == {"light.kitchen", "switch.lamp"}


async def test_value_entity_dict_form(hass: HomeAssistant) -> None:
    """``{"entity": "..."}`` dicts are unwrapped into their entity ID."""
    assert await async_extract_entities_from_value(
        hass, {"entity": "sensor.temperature"}
    ) == {"sensor.temperature"}


async def test_value_template_extracts_referenced_entity(
    hass: HomeAssistant,
) -> None:
    """Template strings have their referenced entity IDs extracted."""
    template = "{{ states('light.kitchen') }}"
    assert await async_extract_entities_from_value(hass, template) == {"light.kitchen"}


async def test_value_template_ignores_concatenated_entity_id_literal(
    hass: HomeAssistant,
) -> None:
    """Templated entity ID fragments are not complete entity references."""
    template = "{{ 'switch.camera' ~ cam_id ~ '_movies' }}"
    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_ignores_jinja_import_filename(
    hass: HomeAssistant,
) -> None:
    """Jinja import filenames are not entity references."""
    template = "{% from 'date.jinja' import how_about_now %}{{ how_about_now() }}"

    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_ignores_jinja_import_as_filename(
    hass: HomeAssistant,
) -> None:
    """Jinja import-as filenames are not entity references."""
    template = "{% import 'date.jinja' as date_helpers %}{{ date_helpers.now() }}"

    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_ignores_whitespace_control_jinja_import_filename(
    hass: HomeAssistant,
) -> None:
    """Jinja import filenames with whitespace control are not entity references."""
    template = "{%- from 'date.jinja' import how_about_now -%}{{ how_about_now() }}"

    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_keeps_entity_reference_between_jinja_blocks(
    hass: HomeAssistant,
) -> None:
    """Entity references in expression blocks are not treated as import filenames."""
    template = (
        "{% from 'date.jinja' import how_about_now %}"
        "{{ states('light.kitchen') }}"
        "{% set finished = true %}"
    )

    assert await async_extract_entities_from_value(hass, template) == {"light.kitchen"}


async def test_value_template_ignores_entity_id_prefix_string_match(
    hass: HomeAssistant,
) -> None:
    """String prefix checks are not complete entity references."""
    template = (
        "{% for entity in states.binary_sensor if "
        "entity.entity_id.startswith('binary_sensor.proxmox') %}"
        "{{ entity.state }}"
        "{% endfor %}"
    )

    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_ignores_grouped_entity_id_prefix_string_match(
    hass: HomeAssistant,
) -> None:
    """String prefix checks can use grouping without becoming references."""
    template = "{{ entity.entity_id.startswith( ('binary_sensor.proxmox')) }}"

    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_ignores_entity_id_suffix_string_match(
    hass: HomeAssistant,
) -> None:
    """String suffix checks are not complete entity references."""
    template = "{{ entity.entity_id.endswith('sensor.power') }}"

    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_ignores_entity_id_in_jinja_comment(
    hass: HomeAssistant,
) -> None:
    """Entity-like strings inside Jinja comments are not active references."""
    template = (
        "{# {{ state_translated('sensor.toothbrush_change_head') | string }} "
        "indicates time to change, toothbrush head #}"
        "{{ trigger.to_state.attributes.friendly_name | string }}"
    )

    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_ignores_concatenated_helper_entity_id(
    hass: HomeAssistant,
) -> None:
    """Helper calls using templated entity IDs do not expose a static entity."""
    template = "{{ is_state('switch.camera' ~ cam_id ~ '_movies', 'on') }}"
    assert await async_extract_entities_from_value(hass, template) == set()


async def test_value_template_keeps_concatenated_state_value(
    hass: HomeAssistant,
) -> None:
    """Concatenated values still expose static entity references."""
    template = "{{ states.light.kitchen.state ~ '_suffix' }}"
    assert await async_extract_entities_from_value(hass, template) == {"light.kitchen"}


async def test_value_template_keeps_concatenated_filtered_entity(
    hass: HomeAssistant,
) -> None:
    """Filtered entity references are kept when their value is concatenated."""
    template = "{{ 'prefix' ~ ('light.kitchen' | states) }}"
    assert await async_extract_entities_from_value(hass, template) == {"light.kitchen"}


async def test_value_non_string_non_collection_returns_empty(
    hass: HomeAssistant,
) -> None:
    """Numbers, booleans, and None yield no entities."""
    assert await async_extract_entities_from_value(hass, 42) == set()
    assert await async_extract_entities_from_value(hass, None) == set()
    value = True
    assert await async_extract_entities_from_value(hass, value) == set()


async def test_trigger_state_entity_id(hass: HomeAssistant) -> None:
    """A state trigger's ``entity_id`` is captured."""
    config = {"platform": "state", "entity_id": "binary_sensor.door"}
    assert await extract_entities_from_trigger_config(hass, config) == {
        "binary_sensor.door"
    }


async def test_trigger_event_type_is_not_an_entity_id(
    hass: HomeAssistant,
) -> None:
    """Event trigger ``event_type`` values are not entity references."""
    config = {
        "platform": "event",
        "event_type": "timer.finished",
        "event_data": {"entity_id": "timer.hot_tub"},
    }
    assert await extract_entities_from_trigger_config(hass, config) == {"timer.hot_tub"}


async def test_event_trigger_type_reference_is_not_reported_unknown(
    hass: HomeAssistant,
) -> None:
    """Event trigger ``event_type`` references are not unknown entities."""
    entity = MockAutomationEntity(
        raw_config={
            "trigger": {
                "platform": "event",
                "event_type": "timer.finished",
                "event_data": {"entity_id": "timer.hot_tub"},
            },
        },
        referenced_entities={"timer.finished", "timer.hot_tub"},
    )
    repair = SpookRepair(hass)
    repair._known_entity_ids = {"timer.hot_tub"}
    # Standing in for `_async_setup_inspection`: the real service set, so
    # action names are still told apart from entity ids.
    repair._known_services = async_get_all_services(hass)

    assert await repair._async_compute_unknown_references(entity) == set()


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


async def test_action_direct_entity_id(hass: HomeAssistant) -> None:
    """A direct ``entity_id`` on an action is captured."""
    config = {"service": "light.turn_on", "entity_id": "light.kitchen"}
    assert await async_extract_entities_from_action_config(hass, config) == {
        "light.kitchen"
    }


async def test_action_target_block(hass: HomeAssistant) -> None:
    """``target.entity_id`` on an action is captured."""
    config = {
        "service": "light.turn_on",
        "target": {"entity_id": ["light.kitchen", "light.living_room"]},
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "light.kitchen",
        "light.living_room",
    }


async def test_action_target_template_entity_id_fragment(hass: HomeAssistant) -> None:
    """A templated ``target.entity_id`` fragment is not treated as an entity."""
    config = {
        "action": "switch.turn_on",
        "target": {"entity_id": "{{ 'switch.camera' ~ cam_id ~ '_movies' }}"},
    }
    assert await async_extract_entities_from_action_config(hass, config) == set()


async def test_action_data_dict(hass: HomeAssistant) -> None:
    """Entities buried inside ``data`` values are captured."""
    config = {
        "service": "light.turn_on",
        "data": {"message": "hello", "target": "person.alice"},
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "person.alice"
    }


async def test_notify_action_data_target_is_not_an_entity_reference(
    hass: HomeAssistant,
) -> None:
    """Notify ``data.target`` values are service targets, not entity references."""
    config = {
        "action": "notify.mobile_app_phone",
        "data": {
            "target": "notify.old_tablet",
            "message": "{{ states('sensor.temperature') }}",
        },
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "sensor.temperature"
    }


async def test_notify_service_data_target_is_not_an_entity_reference(
    hass: HomeAssistant,
) -> None:
    """Legacy service syntax follows the same notify target rule."""
    config = {
        "service": "notify.mobile_app_phone",
        "data": {"target": ["notify.old_tablet", "notify.old_phone"]},
    }
    assert await async_extract_entities_from_action_config(hass, config) == set()


async def test_non_notify_action_data_target_remains_entity_reference(
    hass: HomeAssistant,
) -> None:
    """Non-notify service data is still scanned for entity IDs."""
    config = {
        "action": "calendar.create_event",
        "data": {"target": "person.alice"},
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "person.alice"
    }


async def test_action_data_as_template_string(hass: HomeAssistant) -> None:
    """A template string assigned directly to ``data`` is parsed."""
    config = {
        "service": "notify.notify",
        "data": "{{ states('sensor.temperature') }}",
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "sensor.temperature"
    }


async def test_action_if_then_else_nested(hass: HomeAssistant) -> None:
    """``if``/``then``/``else`` nested actions are walked."""
    config = {
        "if": [{"condition": "state", "entity_id": "binary_sensor.door"}],
        "then": [{"service": "light.turn_on", "target": {"entity_id": "light.hall"}}],
        "else": [{"service": "light.turn_off", "target": {"entity_id": "light.hall"}}],
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "binary_sensor.door",
        "light.hall",
    }


async def test_action_list_of_actions(hass: HomeAssistant) -> None:
    """A top-level list of actions is walked."""
    config = [
        {"service": "light.turn_on", "target": {"entity_id": "light.a"}},
        {"service": "switch.turn_on", "entity_id": "switch.b"},
    ]
    assert await async_extract_entities_from_action_config(hass, config) == {
        "light.a",
        "switch.b",
    }


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


async def test_automation_full_config_with_plural_keys(hass: HomeAssistant) -> None:
    """A modern automation config yields entities from plural sections."""
    config = {
        "alias": "Test",
        "triggers": [{"trigger": "state", "entity_id": "binary_sensor.motion"}],
        "conditions": [
            {
                "condition": "state",
                "entity_id": "input_boolean.snooze_uptime_alerts",
                "state": "off",
            }
        ],
        "actions": [
            {"action": "light.turn_on", "target": {"entity_id": "light.kitchen"}},
        ],
    }

    assert await extract_entities_from_automation_config(hass, config) == {
        "binary_sensor.motion",
        "input_boolean.snooze_uptime_alerts",
        "light.kitchen",
    }


async def test_plural_condition_entity_is_reported_unknown(
    hass: HomeAssistant,
) -> None:
    """A missing entity in a plural ``conditions`` section is reported."""
    entity = MockAutomationEntity(
        raw_config={
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "input_boolean.snooze_uptime_alerts",
                    "state": "off",
                }
            ],
        },
        referenced_entities=set(),
    )
    repair = SpookRepair(hass)
    repair._known_entity_ids = set()
    # Standing in for `_async_setup_inspection`: the real service set, so
    # action names are still told apart from entity ids.
    repair._known_services = async_get_all_services(hass)

    assert await repair._async_compute_unknown_references(entity) == {
        "input_boolean.snooze_uptime_alerts"
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


async def test_state_only_entity_addition_rechecks_automation_repairs(
    hass: HomeAssistant,
) -> None:
    """Test state-only entities trigger automation repair rechecks."""
    repair = SpookRepair(hass)
    await repair.async_activate()
    repair.inspect_debouncer.async_shutdown()
    calls = 0

    def async_schedule_call() -> None:
        """Capture scheduled inspections."""
        nonlocal calls
        calls += 1

    repair.inspect_debouncer = SimpleNamespace(
        async_schedule_call=async_schedule_call,
        async_shutdown=lambda: None,
    )

    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.backup_state",
            "old_state": None,
            "new_state": State("sensor.backup_state", "on"),
        },
    )
    await hass.async_block_till_done()

    assert calls == 1

    await repair.async_deactivate()


async def test_state_only_entity_update_does_not_recheck_automation_repairs(
    hass: HomeAssistant,
) -> None:
    """Test normal state changes do not trigger automation repair rechecks."""
    repair = SpookRepair(hass)
    await repair.async_activate()
    repair.inspect_debouncer.async_shutdown()
    calls = 0

    def async_schedule_call() -> None:
        """Capture scheduled inspections."""
        nonlocal calls
        calls += 1

    repair.inspect_debouncer = SimpleNamespace(
        async_schedule_call=async_schedule_call,
        async_shutdown=lambda: None,
    )

    hass.bus.async_fire(
        EVENT_STATE_CHANGED,
        {
            "entity_id": "sensor.backup_state",
            "old_state": State("sensor.backup_state", "off"),
            "new_state": State("sensor.backup_state", "on"),
        },
    )
    await hass.async_block_till_done()

    assert calls == 0

    await repair.async_deactivate()


def _templated_actions(count: int) -> list[dict]:
    """Return an action list with `count` steps, each holding templates."""
    return [
        {
            "action": "light.turn_on",
            "target": {"entity_id": "{{ 'light.kitchen' }}"},
            "data": {
                "brightness": "{{ states('sensor.brightness') | int(0) }}",
                "transition": "{{ states('sensor.transition') | int(0) }}",
            },
        }
    ] * count


@contextmanager
def _counting_service_lookups() -> Iterator[list[int]]:
    """Count how often the full service registry gets flattened.

    Counted on `ServiceRegistry.async_services`, the expensive call inside
    `async_get_all_services`, rather than on the helper: several modules import
    that helper by name, so patching one of them would miss the others.
    """
    counted = [0]
    real = ServiceRegistry.async_services

    def counting(self: ServiceRegistry) -> dict:
        counted[0] += 1
        return real(self)

    with patch.object(ServiceRegistry, "async_services", counting):
        yield counted


async def test_the_service_set_is_not_rebuilt_per_template(
    hass: HomeAssistant,
) -> None:
    """Building it flattens every service, so it must not follow the config.

    It used to be rebuilt once per template string, which put the cost of a
    repair inspection in proportion to how many templates the automations
    happened to contain. Twenty times for one automation, measured.
    """
    with _counting_service_lookups() as counted:
        await extract_entities_from_automation_config(
            hass, {"action": _templated_actions(1)}
        )
        for_one = counted[0]

        counted[0] = 0
        await extract_entities_from_automation_config(
            hass, {"action": _templated_actions(20)}
        )
        for_twenty = counted[0]

    assert for_twenty == for_one, (
        f"{for_one} rebuild(s) for one action, {for_twenty} for twenty"
    )


async def test_one_inspection_builds_the_service_set_once(
    hass: HomeAssistant,
) -> None:
    """It is the same answer for every automation in one pass.

    Cached in `_async_setup_inspection` next to the known entity ids, so
    adding automations does not add rebuilds.
    """
    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    entity = MockAutomationEntity(
        raw_config={"action": _templated_actions(5)},
        referenced_entities=set(),
    )

    with _counting_service_lookups() as counted:
        for _ in range(10):
            await repair._async_compute_unknown_references(entity)

    assert counted[0] == 0, f"{counted[0]} rebuild(s) while inspecting ten automations"


async def test_a_service_name_in_a_template_survives_the_hand_down(
    hass: HomeAssistant,
) -> None:
    """The set is handed down to be used, not just to be built once.

    A service name written in a template looks exactly like an entity id, and
    the only thing that tells them apart is this set. Handing down an empty
    one would go unnoticed by anything that only counts how often it is built.
    """
    assert await async_setup_component(hass, "input_boolean", {})
    await hass.async_block_till_done()

    entities = await extract_entities_from_automation_config(
        hass,
        {
            "action": [
                {
                    "action": "input_boolean.toggle",
                    "data": {
                        "which": (
                            "{{ states('input_boolean.gate') }}"
                            "{{ 'input_boolean.toggle' }}"
                        ),
                    },
                }
            ],
        },
    )

    assert entities == {"input_boolean.gate"}, "the service name was not filtered out"


async def test_the_action_walker_filters_service_names_without_being_told(
    hass: HomeAssistant,
) -> None:
    """A caller that hands down nothing still gets the filtering.

    Which is the other half: the walker builds the set once itself when it is
    not given one, so an empty set is never what the filtering runs against.
    """
    assert await async_setup_component(hass, "input_boolean", {})
    await hass.async_block_till_done()

    entities = await async_extract_entities_from_action_config(
        hass,
        [
            {
                "action": "input_boolean.toggle",
                "data": {
                    "which": (
                        "{{ states('input_boolean.gate') }}{{ 'input_boolean.toggle' }}"
                    ),
                },
            }
        ],
    )

    assert entities == {"input_boolean.gate"}, "the service name was not filtered out"
