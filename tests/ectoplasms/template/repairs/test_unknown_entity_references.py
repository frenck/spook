"""Tests for the template helper unknown entity references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.template.repairs.unknown_entity_references import (
    SpookRepair,
)
from custom_components.spook.ectoplasms.template.repairs.unknown_service_references import (
    SpookRepair as UnknownServiceReferencesRepair,
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


async def test_unknown_action_in_template_button_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test template button actions referencing deleted scripts are reported."""
    entry = MockConfigEntry(
        domain="template",
        title="Clean everything",
        options={
            "name": "Clean everything",
            "template_type": "button",
            "press": [{"action": "script.1766687627449"}],
        },
    )
    entry.add_to_hass(hass)

    await UnknownServiceReferencesRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_service_references_{entry.entry_id}",
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["services"] == "- `script.1766687627449`"


async def test_unknown_action_in_another_template_helper_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test all template helper action options are inspected."""
    entry = MockConfigEntry(
        domain="template",
        title="Ghostly switch",
        options={
            "name": "Ghostly switch",
            "template_type": "switch",
            "turn_on": [{"action": "script.missing_turn_on"}],
            "turn_off": [{"action": "script.working_turn_off"}],
        },
    )
    entry.add_to_hass(hass)
    hass.services.async_register("script", "working_turn_off", lambda _call: None)

    await UnknownServiceReferencesRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        f"template_unknown_service_references_{entry.entry_id}",
    )
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["services"] == "- `script.missing_turn_on`"
