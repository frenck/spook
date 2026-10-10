"""Tests for leaving automations that are turned off alone."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE_ID = "automation_unknown_entity_references_automation.haunted"


async def _settle(hass: HomeAssistant) -> None:
    """Let the repair's debouncer run the look it was asked for."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_an_automation_is_looked_at_again_as_it_is_turned_on_or_off(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test turning an automation off quiets it, and turning it on brings it back.

    Somebody turned it off, often because something in it is broken, and it
    does nothing while it is off. The moment it is turned back on is when it
    matters, so that is when it is reported again. #1725.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "haunted",
                "alias": "Haunted",
                "triggers": [{"trigger": "event", "event_type": "boo"}],
                "actions": [
                    {"action": "light.turn_on", "target": {"entity_id": "light.ghost"}}
                ],
            }
        },
    )
    await hass.async_block_till_done()
    repair = SpookRepair(hass)
    await repair.async_activate()
    await _settle(hass)
    assert async_issue_about(issue_registry, _ISSUE_ID), "reported while on"

    await hass.services.async_call(
        "automation", "turn_off", {ATTR_ENTITY_ID: "automation.haunted"}, blocking=True
    )
    await _settle(hass)
    assert async_issue_about(issue_registry, _ISSUE_ID) is None, "nagged while off"

    await hass.services.async_call(
        "automation", "turn_on", {ATTR_ENTITY_ID: "automation.haunted"}, blocking=True
    )
    await _settle(hass)
    assert async_issue_about(issue_registry, _ISSUE_ID), "not back once on again"

    await repair.async_deactivate()
