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
from typing import TYPE_CHECKING, Any
from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import ServiceRegistry, State
from homeassistant.helpers.entity_component import DATA_INSTANCES
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


@pytest.mark.parametrize(
    "template",
    [
        # The report in #1686, word for word.
        (
            "{{ [trigger.entity_id | replace('input_boolean.live_override', "
            "'binary_sensor.live')] }}"
        ),
        "{{ trigger.entity_id.replace('binary_sensor.live', 'sensor.live') }}",
        "{{ trigger.entity_id | regex_replace('binary_sensor.live', 'sensor.x') }}",
        "{{ trigger.entity_id | regex_search('binary_sensor.live') }}",
        "{{ trigger.entity_id | regex_match('binary_sensor.live') }}",
        # Parentheses inside a literal do not close the call early.
        "{{ trigger.entity_id | replace('(', '') | replace('sensor.live', '') }}",
        # A Jinja delimiter inside a literal does not start a new block.
        "{{ value | replace('{{', 'sensor.live') }}",
        # Grouping brackets are looked through to the call around them.
        "{{ trigger.entity_id | replace(('sensor.live'), '') }}",
        # The regex tests take a pattern too, negated or not.
        "{{ trigger.entity_id is match('binary_sensor.live') }}",
        "{{ trigger.entity_id is not search('binary_sensor.live') }}",
        # A Windows line ending before it does not shift where it is.
        "before\r\n{{ trigger.entity_id | replace('sensor.live', '') }}",
        # What a substring or pattern test looks for is text. #1838.
        (
            "{{ states.input_boolean | selectattr('entity_id', 'defined')"
            " | selectattr('entity_id', 'contains', 'input_boolean.robovac_run')"
            " | map(attribute='entity_id') | list }}"
        ),
        "{{ states.binary_sensor | rejectattr('entity_id', 'search', 'binary_sensor.100') | list }}",
        "{{ states.light | selectattr('object_id', 'match', 'light.kitchen') | list }}",
        "{{ ids | select('search', 'light.kitchen') | list }}",
        "{{ states.sensor | selectattr('state', 'contains', 'light.kitchen') | list }}",
        # Parentheses that only group the needle change nothing.
        "{{ ids | select('search', ('light.kitchen')) | list }}",
    ],
)
async def test_value_template_ignores_text_function_arguments(
    hass: HomeAssistant,
    template: str,
) -> None:
    """Text passed to replace or a regex filter is not an entity reference."""
    assert await async_extract_entities_from_value(hass, template) == set()


@pytest.mark.parametrize(
    "template",
    [
        # The literal belongs to `states`, the innermost call, not to replace.
        "{{ states('light.kitchen') | replace('on', 'aan') }}",
        "{{ replace(states('light.kitchen'), 'on', 'aan') }}",
        # A replace in an earlier, closed call does not cover what follows.
        "{{ x | replace('a', 'b') }}{{ states('light.kitchen') }}",
        "{{ (x | replace('a', 'b')) ~ states('light.kitchen') }}",
        # An escaped quote does not end the literal it sits in.
        "{{ replace('it\\'s', 'x') ~ states('light.kitchen') }}",
        # Grouping brackets inside a reference do not hide it.
        "{{ states(('light.kitchen')) | replace('on', 'aan') }}",
        # A macro named replace is not the filter, and its argument can be
        # anything, a reference included.
        (
            "{% macro replace(entity_id) %}{{ states(entity_id) }}{% endmacro %}"
            "{{ replace('light.kitchen') }}"
        ),
        # An apostrophe in the prose around a block is not a quote.
        "It's {{ states('light.kitchen') }}, replace('it') later",
        # Exact matches and membership are references, select-style or not.
        "{{ states.light | selectattr('entity_id', 'in', ['light.kitchen']) | list }}",
        "{{ states.light | selectattr('entity_id', 'eq', 'light.kitchen') | list }}",
        (
            "{{ states.group | selectattr('attributes.entity_id', 'contains',"
            " 'light.kitchen') | list }}"
        ),
        # A list inside the call is not the needle, even after a text test.
        "{{ ids | select('search', ['light.kitchen']) | list }}",
        "{{ ids | select('search', ('a', 'light.kitchen')) | list }}",
        # Plain select does not say its items are strings, and on a list
        # `contains` asks about a member.
        "{{ groups | select('contains', 'light.kitchen') | list }}",
    ],
)
async def test_value_template_keeps_references_next_to_text_functions(
    hass: HomeAssistant,
    template: str,
) -> None:
    """A real reference near a replace or regex filter is still found."""
    assert await async_extract_entities_from_value(hass, template) == {"light.kitchen"}


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


async def test_a_message_that_reads_like_an_entity_id_is_just_text(
    hass: HomeAssistant,
) -> None:
    """A notification saying `sensor.example` is not a reference to it.

    Home Assistant sends the message exactly as written. Reporting it as an
    unknown entity is pointing at a sentence.
    """
    config = {
        "action": "persistent_notification.create",
        "data": {"title": "light.porch", "message": "sensor.example"},
    }
    assert await async_extract_entities_from_action_config(hass, config) == set()


async def test_a_field_called_message_elsewhere_is_still_read(
    hass: HomeAssistant,
) -> None:
    """A script or custom action can call a field `message` and mean an entity.

    Only the integrations that define these fields as text get them skipped.
    """
    config = {
        "action": "script.announce_on",
        "data": {"message": "media_player.kitchen"},
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "media_player.kitchen"
    }


async def test_a_template_in_a_message_still_names_what_it_reads(
    hass: HomeAssistant,
) -> None:
    """A message rendering an entity's state does reference that entity."""
    config = {
        "action": "persistent_notification.create",
        "data": {
            "title": "{{ state_attr('light.porch', 'friendly_name') }}",
            "message": "{{ states('sensor.example') }}",
        },
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "light.porch",
        "sensor.example",
    }


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


async def test_a_notification_tag_is_just_text(hass: HomeAssistant) -> None:
    """A notify tag is an id a phone uses to replace an earlier notification.

    It is free text, even when it reads like an entity id. A template in the
    message still names the entity it reads. `notify.send_message` is the same
    domain, so a tag there is text too.
    """
    config = {
        "action": "notify.mobile_app_redmi_note_11s",
        "data": {
            "tag": "notify.waterkoker_inschakelen_notificatie",
            "message": "{{ states('sensor.temperature') }}",
        },
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "sensor.temperature"
    }
    send_message = {
        "action": "notify.send_message",
        "data": {"tag": "notify.waterkoker_inschakelen_notificatie"},
    }
    assert await async_extract_entities_from_action_config(hass, send_message) == set()


async def test_a_notification_tag_on_a_service_is_just_text(
    hass: HomeAssistant,
) -> None:
    """The legacy `service` key names the same notify action as `action`."""
    config = {
        "service": "notify.mobile_app_redmi_note_11s",
        "data": {
            "tag": "notify.waterkoker_inschakelen_notificatie",
            "message": "{{ states('sensor.temperature') }}",
        },
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "sensor.temperature"
    }


async def test_a_notification_tag_nested_under_data_is_just_text(
    hass: HomeAssistant,
) -> None:
    """Mobile app puts the tag under `data.data`, which names no action.

    The notify service from outside still applies, so the tag, a plain
    message, and `target` are not entity references. An `entity_id` there is.
    """
    config = {
        "action": "notify.mobile_app_redmi_note_11s",
        "data": {
            "data": {
                "tag": "notify.waterkoker_inschakelen_notificatie",
                "message": "sensor.example",
                "entity_id": "light.kitchen",
                "target": "notify.old_tablet",
            }
        },
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "light.kitchen"
    }


async def test_a_service_field_in_notify_data_stays_payload(
    hass: HomeAssistant,
) -> None:
    """A `service` key inside notify data is a field, not the action.

    The outer notify action still owns the payload, so a `tag` beside that
    field, and one nested under `data`, stay plain text. A real `entity_id`
    in there is still a reference, and so is a service value that reads like
    an entity id.
    """
    flat = {
        "action": "notify.mobile_app_phone",
        "data": {"service": "script.run", "tag": "notify.example"},
    }
    nested = {
        "action": "notify.mobile_app_phone",
        "data": {
            "service": "script.run",
            "data": {
                "tag": "notify.example",
                "target": "notify.old_tablet",
                "entity_id": "light.kitchen",
            },
        },
    }
    assert await async_extract_entities_from_action_config(hass, flat) == {"script.run"}
    assert await async_extract_entities_from_action_config(hass, nested) == {
        "light.kitchen",
        "script.run",
    }


async def test_a_template_in_a_notification_tag_still_names_what_it_reads(
    hass: HomeAssistant,
) -> None:
    """A tag rendered from an entity's state does reference that entity.

    The same for a tag on the action data and one nested in the mobile app
    payload, which has no action name of its own.
    """
    flat = {
        "action": "notify.mobile_app_phone",
        "data": {"tag": "{{ states('sensor.example') }}"},
    }
    nested = {
        "action": "notify.mobile_app_phone",
        "data": {"data": {"tag": "{{ states('sensor.example') }}"}},
    }
    assert await async_extract_entities_from_action_config(hass, flat) == {
        "sensor.example"
    }
    assert await async_extract_entities_from_action_config(hass, nested) == {
        "sensor.example"
    }


async def test_a_field_called_tag_elsewhere_is_still_read(
    hass: HomeAssistant,
) -> None:
    """`tag` is text for notify alone.

    A script can call a field `tag` and mean an entity. So can tts, which
    shares the message and title exception but not this one.
    """
    script = {
        "action": "script.announce_on",
        "data": {"tag": "media_player.kitchen"},
    }
    tts = {
        "action": "tts.speak",
        "data": {"tag": "media_player.kitchen"},
    }
    assert await async_extract_entities_from_action_config(hass, script) == {
        "media_player.kitchen"
    }
    assert await async_extract_entities_from_action_config(hass, tts) == {
        "media_player.kitchen"
    }


async def test_a_logger_name_is_just_text(hass: HomeAssistant) -> None:
    """`system_log.write` files a line under a logger name, which is text.

    So is the message. The next action in the same list is a different
    service, and the entity it names is still a reference.
    """
    assert (
        await async_extract_entities_from_action_config(
            hass,
            {
                "action": "system_log.write",
                "data": {
                    "logger": "automation.debug",
                    "message": "sensor.example",
                },
            },
        )
        == set()
    )
    sequence = [
        {
            "action": "system_log.write",
            "data": {"logger": "automation.debug", "message": "sensor.example"},
        },
        {"action": "light.turn_on", "entity_id": "light.kitchen"},
    ]
    assert await async_extract_entities_from_action_config(hass, sequence) == {
        "light.kitchen"
    }


async def test_a_template_in_a_logger_name_still_names_what_it_reads(
    hass: HomeAssistant,
) -> None:
    """A logger name rendered from an entity's state does reference that entity."""
    config = {
        "action": "system_log.write",
        "data": {"logger": "{{ states('sensor.example') }}"},
    }
    assert await async_extract_entities_from_action_config(hass, config) == {
        "sensor.example"
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


async def test_a_custom_event_payload_is_not_a_reference(
    hass: HomeAssistant,
) -> None:
    """An `entity_id` in somebody's own event is data, not a dependency.

    Reporting it would be a repair about an automation that works, which is
    the worst thing to get wrong. Home Assistant's own reading does take it,
    so the repair also takes it back out of that: see
    `test_a_custom_event_payload_is_no_unknown_entity`.
    """
    config = {
        "platform": "event",
        "event_type": "my_external_event",
        "event_data": {"entity_id": "light.whatever_the_sender_calls_it"},
    }

    assert await extract_entities_from_trigger_config(hass, config) == set()


async def test_an_integration_event_payload_still_is_one(
    hass: HomeAssistant,
) -> None:
    """`timer.finished` names a domain, so its payload means an entity.

    That is the line between the two: an event named after an integration
    comes from it and says what it means.
    """
    config = {
        "platform": "event",
        "event_type": "timer.finished",
        "event_data": {"entity_id": "timer.hot_tub"},
    }

    assert await extract_entities_from_trigger_config(hass, config) == {"timer.hot_tub"}


async def _async_automation_entity(hass: HomeAssistant, config: dict) -> Any:
    """Load one automation the way Home Assistant does, and return its entity."""
    assert await async_setup_component(
        hass, "automation", {"automation": {"id": "spooky", **config}}
    )
    await hass.async_block_till_done()
    (entity,) = hass.data[DATA_INSTANCES]["automation"].entities
    return entity


async def test_a_custom_event_payload_is_no_unknown_entity(
    hass: HomeAssistant,
) -> None:
    """Test the entity in somebody's own event is not reported.

    Home Assistant's own reading takes it, from any event trigger: that is
    the premise, so it is checked here too.
    """
    entity = await _async_automation_entity(
        hass,
        {
            "alias": "Remote",
            "triggers": [
                {
                    "trigger": "event",
                    "event_type": "my_remote_pressed",
                    "event_data": {"entity_id": "light.from_the_remote"},
                }
            ],
            "actions": [],
        },
    )
    assert "light.from_the_remote" in entity.referenced_entities

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_a_custom_event_payload_named_elsewhere_still_counts(
    hass: HomeAssistant,
) -> None:
    """Test an entity in the payload that is also used for real is reported."""
    entity = await _async_automation_entity(
        hass,
        {
            "alias": "Remote",
            "triggers": [
                {
                    "trigger": "event",
                    "event_type": "my_remote_pressed",
                    "event_data": {"entity_id": "light.from_the_remote"},
                }
            ],
            "actions": [
                {
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.from_the_remote"},
                }
            ],
        },
    )

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == {
        "light.from_the_remote"
    }


async def test_an_integration_event_payload_is_still_reported(
    hass: HomeAssistant,
) -> None:
    """Test the entity in an integration's own event still is a reference."""
    entity = await _async_automation_entity(
        hass,
        {
            "alias": "Timer done",
            "triggers": [
                {
                    "trigger": "event",
                    "event_type": "timer.finished",
                    "event_data": {"entity_id": "timer.laundry"},
                }
            ],
            "actions": [],
        },
    )

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == {"timer.laundry"}


async def _async_unknown_in_automation(hass: HomeAssistant, config: dict) -> set[str]:
    """Load one automation the way Home Assistant does, and ask the repair."""
    assert await async_setup_component(hass, "automation", {"automation": config})
    await hass.async_block_till_done()
    (entity,) = hass.data[DATA_INSTANCES]["automation"].entities

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()
    return await repair._async_compute_unknown_references(entity)


async def test_text_that_is_never_rendered_names_no_entity(
    hass: HomeAssistant,
) -> None:
    """Test an example template in a description or a name is not read.

    Home Assistant shows those, it never renders them. Issue #1082.
    """
    config: dict[str, Any] = {
        "alias": "Porch light",
        "description": "Uses {{ states('sensor.your_entity_last_turned_on') }}",
        "triggers": [{"trigger": "homeassistant", "event": "start"}],
        "actions": [
            {
                "alias": "Was {{ states('sensor.step_name_example') }}",
                "delay": 1,
            }
        ],
    }

    assert await _async_unknown_in_automation(hass, config) == set()


async def test_a_template_in_action_data_still_names_entities(
    hass: HomeAssistant,
) -> None:
    """Test a `description` in action data is rendered, so it is still read."""
    config: dict[str, Any] = {
        "alias": "Calendar",
        "triggers": [{"trigger": "homeassistant", "event": "start"}],
        "actions": [
            {
                "action": "calendar.create_event",
                "target": {"entity_id": "calendar.home"},
                "data": {
                    "summary": "Laundry",
                    "description": "{{ states('sensor.washing_machine_ghost') }}",
                },
            }
        ],
    }

    assert "sensor.washing_machine_ghost" in await _async_unknown_in_automation(
        hass, config
    )


_PUMP_CHECK: dict[str, Any] = {
    "alias": "Pump",
    "triggers": [{"trigger": "homeassistant", "event": "start"}],
    "conditions": [
        {
            "condition": "template",
            "value_template": "{{ states('sensor.Pump_Interval') }}",
        }
    ],
    "actions": [],
}


async def test_a_mixed_case_lookup_of_a_missing_entity_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test a state lookup in mixed case is checked, as the entity it reads.

    Home Assistant tries the lower case entity ID for a state lookup, so this
    template reads `sensor.pump_interval`, and that one is gone.
    """
    assert await _async_unknown_in_automation(hass, _PUMP_CHECK) == {
        "sensor.pump_interval"
    }


async def test_a_mixed_case_lookup_of_an_existing_entity_is_fine(
    hass: HomeAssistant,
) -> None:
    """Test a state lookup in mixed case of an entity that is there is clean."""
    hass.states.async_set("sensor.pump_interval", "30")

    assert await _async_unknown_in_automation(hass, _PUMP_CHECK) == set()


_PUMP_LOOKUPS = pytest.mark.parametrize(
    "template",
    [
        "{{ 'sensor.Pump_Interval' | states }}",
        "{{ 'sensor.Pump_Interval' is has_value }}",
        "{{ expand('sensor.pump_speed', ['sensor.Pump_Interval']) | count }}",
    ],
)


def _pump_check(template: str) -> dict[str, Any]:
    """Return the pump automation, checking this template instead."""
    return {
        **_PUMP_CHECK,
        "conditions": [{"condition": "template", "value_template": template}],
    }


@_PUMP_LOOKUPS
async def test_a_mixed_case_lookup_in_any_form_of_a_missing_entity_is_reported(
    hass: HomeAssistant, template: str
) -> None:
    """Test a mixed case lookup as a filter, a test or a later argument.

    Each reads `sensor.pump_interval`, the same as `states(...)` does.
    """
    hass.states.async_set("sensor.pump_speed", "1")

    assert await _async_unknown_in_automation(hass, _pump_check(template)) == {
        "sensor.pump_interval"
    }


@_PUMP_LOOKUPS
async def test_a_mixed_case_lookup_in_any_form_of_an_existing_entity_is_fine(
    hass: HomeAssistant, template: str
) -> None:
    """Test those same lookups are clean when the entity is there."""
    hass.states.async_set("sensor.pump_speed", "1")
    hass.states.async_set("sensor.pump_interval", "30")

    assert await _async_unknown_in_automation(hass, _pump_check(template)) == set()


async def test_a_mixed_case_key_in_front_of_a_lookup_filter_is_no_entity(
    hass: HomeAssistant,
) -> None:
    """Test a key looked up in a mapping before `expand` is not the entity.

    `expand` gets what is stored under the key, not the key itself.
    """
    hass.states.async_set("sensor.pump_speed", "1")
    template = (
        "{% set pumps = {'sensor.Pump_Interval': ['sensor.pump_speed']} %}"
        "{{ pumps['sensor.Pump_Interval'] | expand | count }}"
    )

    assert await _async_unknown_in_automation(hass, _pump_check(template)) == set()


@pytest.mark.parametrize(
    "event_type",
    ["state_changed", "state_reported", "automation_triggered", "script_started"],
)
async def test_a_payload_home_assistant_fires_about_an_entity_is_reported(
    hass: HomeAssistant, event_type: str
) -> None:
    """Test the entity in an event Home Assistant fires about it is a reference.

    These are not named after a domain, but Home Assistant puts the entity
    they are about in `entity_id`. Waiting for one of a missing entity never
    fires.
    """
    entity = await _async_automation_entity(
        hass,
        {
            "alias": "Watch",
            "triggers": [
                {
                    "trigger": "event",
                    "event_type": event_type,
                    "event_data": {"entity_id": "light.gone"},
                }
            ],
            "actions": [],
        },
    )

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == {"light.gone"}


async def test_a_literal_glued_to_more_with_plus_is_no_entity(
    hass: HomeAssistant,
) -> None:
    """Test `'sensor.room' + suffix` is the start of an entity ID, not one.

    Jinja glues two strings with `+` as well as with `~`. The automation
    reads `sensor.room_bedroom_temperature`, never `sensor.room`.
    """
    hass.states.async_set("sensor.room_bedroom_temperature", "21")
    entity = await _async_automation_entity(
        hass,
        {
            "alias": "Report",
            "triggers": [{"trigger": "homeassistant", "event": "start"}],
            "actions": [
                {
                    "action": "notify.notify",
                    "data": {
                        "message": (
                            "{% set suffix = '_bedroom_temperature' %}"
                            "{{ states('sensor.room' + suffix) }}"
                        )
                    },
                }
            ],
        },
    )

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_a_filtered_literal_added_to_is_an_entity(
    hass: HomeAssistant,
) -> None:
    """Test `10 + 'sensor.pump' | states` looks up `sensor.pump`.

    The filter binds tighter than the `+`, so it gets the literal alone, and
    the `+` adds up the number that comes out. The literal glued to a
    variable right after it is still only the start of an entity ID.
    """
    hass.states.async_set("sensor.pump_bedroom", "3")
    entity = await _async_automation_entity(
        hass,
        {
            "alias": "Report",
            "triggers": [{"trigger": "homeassistant", "event": "start"}],
            "actions": [
                {
                    "action": "notify.notify",
                    "data": {
                        "message": (
                            "{% set suffix = '_bedroom' %}"
                            "{{ 10 + 'sensor.pump' | states | float(0) }}"
                            "{{ states('sensor.pump' ~ suffix) }}"
                        )
                    },
                }
            ],
        },
    )

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == {"sensor.pump"}


def _log_location(action: dict[str, Any]) -> dict[str, Any]:
    """Return an automation that hands a sensor to a script in one action."""
    return {
        "alias": "Log location",
        "triggers": [{"trigger": "homeassistant", "event": "start"}],
        "actions": [action],
    }


@pytest.mark.parametrize("data_key", ["data", "data_template"])
async def test_a_script_field_handed_over_by_turn_on_is_reported(
    hass: HomeAssistant, data_key: str
) -> None:
    """Test an entity in the variables script.turn_on hands over is read.

    Home Assistant gives those to the script exactly like the data of a
    direct call to it, so a missing entity in there is just as broken. The
    old `data_template` is merged into the data, so it counts the same.
    """
    hass.states.async_set("script.google_location", "off")

    config = _log_location(
        {
            "action": "script.turn_on",
            "target": {"entity_id": "script.google_location"},
            data_key: {
                "variables": {
                    "worksheet": "LocationLog",
                    "sensor": "sensor.member_one_address",
                }
            },
        }
    )

    assert await _async_unknown_in_automation(hass, config) == {
        "sensor.member_one_address"
    }


async def test_a_script_field_handed_over_directly_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test the same field in the data of a direct call to the script."""
    hass.states.async_set("script.google_location", "off")

    config = _log_location(
        {
            "action": "script.google_location",
            "data": {
                "worksheet": "LocationLog",
                "sensor": "sensor.member_one_address",
            },
        }
    )

    assert await _async_unknown_in_automation(hass, config) == {
        "sensor.member_one_address"
    }


async def test_a_field_called_variables_elsewhere_is_not_dug_into(
    hass: HomeAssistant,
) -> None:
    """Test only script.turn_on gets its variables read a level deeper.

    For a direct call, `variables` is just a field of the script, and what
    is nested in a field is the script's business.
    """
    hass.states.async_set("script.google_location", "off")

    config = _log_location(
        {
            "action": "script.google_location",
            "data": {"variables": {"sensor": "sensor.member_one_address"}},
        }
    )

    assert await _async_unknown_in_automation(hass, config) == set()


# The corpus case: a threshold is read from a helper, both on the trigger and
# on a condition. The thresholds themselves are gone, the rest is there.
_THRESHOLD_HELPERS: dict[str, Any] = {
    "alias": "Keep minimum below maximum",
    "triggers": [
        {
            "trigger": "numeric_state",
            "entity_id": "input_number.alarm_temperature_min",
            "above": "input_number.alarm_temperature_max",
        }
    ],
    "conditions": [
        {
            "condition": "numeric_state",
            "entity_id": "sensor.freezer_temperature",
            "below": "input_number.freezer_limit",
        }
    ],
    "actions": [
        {
            "if": [
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.freezer_temperature",
                    "above": "sensor.freezer_alarm",
                }
            ],
            "then": [{"delay": 0}],
        }
    ],
}


async def test_a_missing_numeric_state_threshold_entity_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test the entity a numeric state threshold is read from is a reference.

    Home Assistant compares against its state, and with it gone the trigger
    and the conditions fail. Its own reading only takes `entity_id`.
    """
    hass.states.async_set("input_number.alarm_temperature_min", "1")
    hass.states.async_set("sensor.freezer_temperature", "-18")

    assert await _async_unknown_in_automation(hass, _THRESHOLD_HELPERS) == {
        "input_number.alarm_temperature_max",
        "input_number.freezer_limit",
        "sensor.freezer_alarm",
    }


async def test_a_numeric_state_threshold_that_is_a_number_is_no_entity(
    hass: HomeAssistant,
) -> None:
    """Test a plain number as a threshold is no entity, and one that is there is fine.

    Home Assistant takes the entity ID in lower case, so a mixed case one
    reads the helper that is there.
    """
    hass.states.async_set("sensor.freezer_temperature", "-18")
    hass.states.async_set("input_number.freezer_limit", "-15")

    config: dict[str, Any] = {
        "alias": "Freezer",
        "triggers": [
            {
                "trigger": "numeric_state",
                "entity_id": "sensor.freezer_temperature",
                "above": -30,
                "below": "input_number.Freezer_Limit",
            }
        ],
        "actions": [],
    }

    assert await _async_unknown_in_automation(hass, config) == set()


# Shaped like a numeric state condition, yet only a value somebody hands over.
_LOOKS_LIKE_A_THRESHOLD = {"condition": "numeric_state", "above": "sensor.label"}


@pytest.mark.parametrize(
    ("triggers", "actions"),
    [
        pytest.param(
            [
                {
                    "trigger": "event",
                    "event_type": "timer.finished",
                    "event_data": {"entity_id": "timer.tea", **_LOOKS_LIKE_A_THRESHOLD},
                }
            ],
            [],
            id="event_data of an integration event trigger",
        ),
        pytest.param(
            [
                {
                    "trigger": "state",
                    "entity_id": "timer.tea",
                    "variables": {"limit": _LOOKS_LIKE_A_THRESHOLD},
                }
            ],
            [],
            id="variables of a trigger",
        ),
        pytest.param(
            [],
            [{"event": "label_printed", "event_data": _LOOKS_LIKE_A_THRESHOLD}],
            id="event_data of an event action",
        ),
        pytest.param(
            [],
            [
                {
                    "event": "label_printed",
                    "event_data_template": _LOOKS_LIKE_A_THRESHOLD,
                }
            ],
            id="event_data_template of an event action",
        ),
        pytest.param(
            [],
            [{"variables": {"limit": _LOOKS_LIKE_A_THRESHOLD}}],
            id="variables step",
        ),
        pytest.param(
            [],
            [
                {
                    "action": "script.label_printer",
                    "data": {"limit": _LOOKS_LIKE_A_THRESHOLD},
                }
            ],
            id="action data",
        ),
        pytest.param(
            [],
            [
                {
                    "action": "script.label_printer",
                    "data_template": {"limit": _LOOKS_LIKE_A_THRESHOLD},
                }
            ],
            id="old style action data",
        ),
        pytest.param(
            [],
            [
                {
                    "repeat": {
                        "for_each": [_LOOKS_LIKE_A_THRESHOLD],
                        "sequence": [{"delay": 0}],
                    }
                }
            ],
            id="for_each items",
        ),
        pytest.param(
            [],
            [
                {
                    "wait_for_trigger": [
                        {
                            "trigger": "event",
                            "event_type": "timer.finished",
                            "event_data": {
                                "entity_id": "timer.tea",
                                **_LOOKS_LIKE_A_THRESHOLD,
                            },
                        }
                    ]
                }
            ],
            id="event_data of a trigger waited for",
        ),
    ],
)
async def test_a_value_shaped_like_a_threshold_is_no_reference(
    hass: HomeAssistant, triggers: list[Any], actions: list[Any]
) -> None:
    """Test a value that looks like a numeric state condition is left alone.

    Event data, variables, action data and the items a repeat goes over hold
    whatever somebody put there. Only a real trigger or condition has a
    threshold.
    """
    hass.states.async_set("timer.tea", "idle")
    config: dict[str, Any] = {
        "alias": "Labels",
        "triggers": triggers or [{"trigger": "homeassistant", "event": "start"}],
        "actions": actions,
    }

    assert await _async_unknown_in_automation(hass, config) == set()
    # Home Assistant takes the configuration, so this is one that works.
    assert hass.states.get("automation.labels").state == "on"


def _logbook_automation(entity_id: str) -> dict[str, Any]:
    """Return an automation filing a logbook entry under ``entity_id``."""
    return {
        "alias": "Log critical messages",
        "triggers": [{"trigger": "homeassistant", "event": "start"}],
        "actions": [
            {
                "action": "logbook.log",
                "data": {
                    "entity_id": entity_id,
                    "name": "Alert",
                    "message": "Water on the floor",
                },
            }
        ],
    }


async def test_a_made_up_entity_to_file_a_logbook_entry_under_is_fine(
    hass: HomeAssistant,
) -> None:
    """Test `logbook.log` under an ID no integration provides is not reported.

    The action only checks the shape of the ID, and a logbook card filters on
    it. Home Assistant's own reading takes it: that is the premise, so it is
    checked here too.
    """
    entity = await _async_automation_entity(
        hass, _logbook_automation("log.critical_messages")
    )
    assert "log.critical_messages" in entity.referenced_entities

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_a_removed_entity_to_file_a_logbook_entry_under_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test `logbook.log` under a real domain still checks the entity."""
    entity = await _async_automation_entity(hass, _logbook_automation("light.gone"))

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == {"light.gone"}


async def test_a_made_up_logbook_entity_also_used_as_a_target_is_reported(
    hass: HomeAssistant,
) -> None:
    """Test the same made-up ID used as a target too is still reported.

    Filing a logbook entry under it is fine, turning it on is not: as a
    target it is a reference, and a missing one.
    """
    config = _logbook_automation("log.critical_messages")
    config["actions"].append(
        {
            "action": "homeassistant.turn_on",
            "target": {"entity_id": "log.critical_messages"},
        }
    )
    entity = await _async_automation_entity(hass, config)

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == {
        "log.critical_messages"
    }


async def test_a_logbook_step_in_action_data_is_no_step(
    hass: HomeAssistant,
) -> None:
    """Test a `logbook.log` shaped mapping in action data exempts nothing.

    It is whatever the called action takes, not a step. The same ID handed
    over as data of a real call stays a reference.
    """
    entity = await _async_automation_entity(
        hass,
        {
            "alias": "Relay",
            "triggers": [{"trigger": "homeassistant", "event": "start"}],
            "actions": [
                {
                    "action": "homeassistant.turn_on",
                    "target": {"entity_id": "log.critical_messages"},
                    "data": {
                        "step": {
                            "action": "logbook.log",
                            "data": {"entity_id": "log.critical_messages"},
                        }
                    },
                }
            ],
        },
    )

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == {
        "log.critical_messages"
    }


async def test_a_made_up_entity_outside_the_logbook_is_still_reported(
    hass: HomeAssistant,
) -> None:
    """Test an ID under no entity domain is still reported as a target."""
    entity = await _async_automation_entity(
        hass,
        {
            "alias": "Turn on",
            "triggers": [{"trigger": "homeassistant", "event": "start"}],
            "actions": [
                {
                    "action": "homeassistant.turn_on",
                    "target": {"entity_id": "log.critical_messages"},
                }
            ],
        },
    )

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == {
        "log.critical_messages"
    }


async def test_a_logbook_entry_filed_under_the_action_name_is_fine(
    hass: HomeAssistant,
) -> None:
    """Test the name of the action is no use of an entity of that name.

    `logbook.log` is under no entity domain either, so filing an entry under
    it is as harmless as under any other made-up ID.
    """
    entity = await _async_automation_entity(hass, _logbook_automation("logbook.log"))
    assert "logbook.log" in entity.referenced_entities

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()


async def test_an_event_payload_and_a_logbook_entry_do_not_cancel_out(
    hass: HomeAssistant,
) -> None:
    """Test two harmless mentions of the same ID together stay harmless.

    Listening for somebody's own event carrying it, and filing a logbook
    entry under it: neither is a use, so one is no use of the other either.
    """
    config = _logbook_automation("log.critical_messages")
    config["triggers"] = [
        {
            "trigger": "event",
            "event_type": "my_alarm",
            "event_data": {"entity_id": "log.critical_messages"},
        }
    ]
    entity = await _async_automation_entity(hass, config)
    assert "log.critical_messages" in entity.referenced_entities

    repair = SpookRepair(hass)
    await repair._async_setup_inspection()

    assert await repair._async_compute_unknown_references(entity) == set()
