"""Tests for the automation unknown trigger references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.automation.repairs.unknown_trigger_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def test_broken_automation_gets_a_specific_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an automation with an unavailable trigger is named precisely.

    An automation using a trigger from a removed integration fails
    validation and becomes unavailable; the repair must inspect it
    anyway and name the offending trigger.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": [{"trigger": "ghost_integration.appeared"}],
                    "actions": [{"action": "light.turn_on"}],
                },
                {
                    "id": "healthy",
                    "alias": "Healthy",
                    "triggers": [
                        {"trigger": "state", "entity_id": "binary_sensor.motion"},
                    ],
                    "actions": [{"action": "light.turn_on"}],
                },
            ],
        },
    )
    await hass.async_block_till_done()

    # The broken automation failed validation and is unavailable.
    state = hass.states.get("automation.haunted")
    assert state
    assert state.state == "unavailable"

    repair = SpookRepair(hass)
    await repair.async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "automation_unknown_trigger_references_automation.haunted",
    )
    assert issue
    assert issue.translation_placeholders
    assert (
        issue.translation_placeholders["triggers"] == "- `ghost_integration.appeared`"
    )

    assert (
        issue_registry.async_get_issue(
            DOMAIN,
            "automation_unknown_trigger_references_automation.healthy",
        )
        is None
    )
