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
