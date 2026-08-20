"""Tests for the template helper unknown action references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.template.repairs.unknown_service_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


def _issue_id(entry: MockConfigEntry) -> str:
    """Return the repair issue ID for a config entry."""
    return f"template_unknown_service_references_{entry.entry_id}"


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

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["edit"] == "/config/helpers"
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

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["services"] == "- `script.missing_turn_on`"


async def test_templated_action_in_template_helper_creates_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test templated actions in raw template helper options are ignored."""
    entry = MockConfigEntry(
        domain="template",
        title="Dynamic notification",
        options={
            "name": "Dynamic notification",
            "template_type": "button",
            "press": [{"action": "{{ 'notify.' ~ who }}"}],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None
