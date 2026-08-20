"""Tests for the template helper unknown entity references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.template.repairs.unknown_entity_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def test_unknown_entity_in_template_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a template helper referencing a nonexistent entity is reported."""
    entry = MockConfigEntry(
        domain="template",
        title="Ghostly sensor",
        options={
            "name": "Ghostly sensor",
            "template_type": "sensor",
            "state": "{{ states('sensor.ghost') | float + 1 }}",
            "availability": "{{ has_value('binary_sensor.also_ghost') }}",
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entities"] == (
        "- `binary_sensor.also_ghost`\n- `sensor.ghost`"
    )


async def test_known_entities_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a template helper referencing existing entities is not reported."""
    hass.states.async_set("sensor.real", "1")

    entry = MockConfigEntry(
        domain="template",
        title="Fine sensor",
        options={
            "name": "Fine sensor",
            "template_type": "sensor",
            "state": "{{ states('sensor.real') | float + 1 }}",
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert (
        issue_registry.async_get_issue(
            DOMAIN,
            f"template_unknown_entity_references_{entry.entry_id}",
        )
        is None
    )


async def test_unknown_entity_in_action_target_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an action target referencing a nonexistent entity is reported.

    The service itself exists, and the entity is in structured config rather
    than in a template, so neither the service check nor the template
    extraction would notice it.
    """
    entry = MockConfigEntry(
        domain="template",
        title="Ghostly button",
        options={
            "name": "Ghostly button",
            "template_type": "button",
            "press": [
                {
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.ghost"},
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["entities"] == "- `light.ghost`"


async def test_known_entity_in_action_target_creates_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an action target referencing an existing entity is not reported."""
    hass.states.async_set("light.real", "off")

    entry = MockConfigEntry(
        domain="template",
        title="Fine switch",
        options={
            "name": "Fine switch",
            "template_type": "switch",
            "state": "{{ is_state('light.real', 'on') }}",
            "turn_on": [
                {"action": "light.turn_on", "target": {"entity_id": "light.real"}},
            ],
            "turn_off": [
                {"action": "light.turn_off", "target": {"entity_id": "light.real"}},
            ],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert not issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )


async def test_non_action_options_create_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test option values that are not action sequences are not misread.

    Options are scanned generically rather than by a fixed field list, so a
    plain list of strings that happen to look like entity IDs must not be
    mistaken for references.
    """
    entry = MockConfigEntry(
        domain="template",
        title="Fine select",
        options={
            "name": "Fine select",
            "template_type": "select",
            "state": "{{ 'a' }}",
            "options": "{{ ['a', 'b'] }}",
            "unit_of_measurement": "sensor.not_a_reference",
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert not issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )


async def test_disabled_step_reference_is_qualified(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a reference only a disabled step makes is marked as such."""
    entry = MockConfigEntry(
        domain="template",
        title="Half-retired button",
        options={
            "name": "Half-retired button",
            "template_type": "button",
            "press": [
                {
                    "action": "light.turn_on",
                    "target": {"entity_id": "light.gone_live"},
                },
                {
                    "action": "light.turn_on",
                    "enabled": False,
                    "target": {"entity_id": "light.gone_retired"},
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )
    assert issue
    entities = issue.translation_placeholders["entities"]
    assert "light.gone_live" in entities
    assert "light.gone_retired" in entities
    # Only the disabled one carries the qualifier. Select each line by its
    # entity ID, so a failure names the entity rather than the block order.
    lines = entities.splitlines()
    live = next(line for line in lines if "gone_live" in line)
    retired = next(line for line in lines if "gone_retired" in line)
    assert "only referenced from disabled steps" not in live
    assert "only referenced from disabled steps" in retired


async def test_disabled_step_only_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a helper whose only bad reference is disabled is still reported.

    Disabled steps come back: a seasonal device parked for half a year is
    still a broken reference waiting to happen, so it is qualified, not
    dropped.
    """
    entry = MockConfigEntry(
        domain="template",
        title="Parked button",
        options={
            "name": "Parked button",
            "template_type": "button",
            "press": [
                {
                    "action": "light.turn_on",
                    "enabled": False,
                    "target": {"entity_id": "light.seasonal"},
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )
    assert issue
    entities = issue.translation_placeholders["entities"]
    assert "light.seasonal" in entities
    assert "only referenced from disabled steps" in entities


async def test_enabled_key_in_service_data_is_not_a_disabled_step(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an `enabled` key inside a payload does not disable its surroundings.

    Only list members are steps. A service data payload carrying its own
    `enabled` field must not hide the entities nested around it.
    """
    entry = MockConfigEntry(
        domain="template",
        title="Payload button",
        options={
            "name": "Payload button",
            "template_type": "button",
            "press": [
                {
                    "action": "test.service",
                    "data": {"payload": {"enabled": False, "entity_id": "light.gone"}},
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )
    assert issue
    entities = issue.translation_placeholders["entities"]
    assert "light.gone" in entities
    assert "only referenced from disabled steps" not in entities


async def test_enabled_key_in_payload_list_is_not_a_disabled_step(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an `enabled` key in a payload list does not disable its surroundings.

    Service data is arbitrary payload, and a list in there is not a sequence
    of steps. Only the dict case was pinned down before, which left a list
    one level deeper reported as disabled while nothing was disabled.
    """
    entry = MockConfigEntry(
        domain="template",
        title="Payload list button",
        options={
            "name": "Payload list button",
            "template_type": "button",
            "press": [
                {
                    "action": "mqtt.publish",
                    "data": {
                        "payload": {
                            "items": [{"enabled": False, "entity_id": "light.gone"}],
                        },
                    },
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )
    assert issue
    entities = issue.translation_placeholders["entities"]
    assert "light.gone" in entities
    assert "only referenced from disabled steps" not in entities


async def test_templated_enabled_counts_as_active(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a step whose `enabled` is a template is treated as running."""
    entry = MockConfigEntry(
        domain="template",
        title="Maybe button",
        options={
            "name": "Maybe button",
            "template_type": "button",
            "press": [
                {
                    "action": "light.turn_on",
                    "enabled": "{{ 1 == 2 }}",
                    "target": {"entity_id": "light.gone"},
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_entity_references_{entry.entry_id}",
    )
    assert issue
    entities = issue.translation_placeholders["entities"]
    assert "light.gone" in entities
    assert "only referenced from disabled steps" not in entities
