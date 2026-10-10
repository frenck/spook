"""Tests for the automation unknown state references repair."""

# pylint: disable=wrong-import-order,protected-access
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.components.light import LightEntity
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook.ectoplasms.automation.repairs.unknown_state_references import (
    SpookRepair,
)
from tests.entity_objects import give_entity_objects
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "automation_unknown_state_references_automation.haunted"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    recorder_db_url: str,
    enable_custom_integrations: None,
) -> None:
    """Prepare the recorder's database before Home Assistant starts.

    The recorder fixtures insist on going first, and the shared fixture that
    enables custom integrations starts Home Assistant.
    """
    _ = recorder_db_url, enable_custom_integrations


async def _automation(hass: HomeAssistant, **trigger: Any) -> None:
    """Set up an automation triggering on the state of the kitchen light."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": [
                        {"trigger": "state", "entity_id": "light.kitchen", **trigger}
                    ],
                    "actions": [],
                }
            ]
        },
    )
    await hass.async_block_till_done()


async def test_case_only_is_reported_without_a_recorder(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a difference in case alone is reported, recorder or not."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "off")
    await _automation(hass, to="On")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "automation_unknown_state_references"
    assert issue.translation_placeholders == {
        "automation": "Haunted",
        "edit": "/config/automation/edit/haunted",
        "entity_id": "automation.haunted",
        "states": "- `On` for `light.kitchen` (did you mean `on`?)",
    }


async def test_without_a_recorder_only_case_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a state nobody can rule out is not reported without history."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "off")
    await _automation(hass, to="dimmed")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_state_set_from_outside_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a light whose state its integration did not set is not judged."""
    hass.states.async_set("light.kitchen", "off")
    await _automation(hass, to="On")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_state_never_had_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a state the entity is never in is reported, from history."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "on")
    hass.states.async_set("light.kitchen", "off")
    await async_wait_recording_done(hass)
    await _automation(hass, **{"from": "dimmed"})

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["states"] == "- `dimmed` for `light.kitchen`"


@pytest.mark.usefixtures("recorder_mock")
async def test_state_only_in_history_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a state the entity was once in, outside of its set, is fine."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "dimmed")
    hass.states.async_set("light.kitchen", "off")
    await async_wait_recording_done(hass)
    await _automation(hass, to="dimmed")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_fixed_is_cleared(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes once the entity turns out to be in that state."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "off")
    await _automation(hass, to="On")

    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, ISSUE)

    hass.states.async_set("light.kitchen", "On")
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, ISSUE) is None


async def test_not_before_the_recorder_settles(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test nothing is looked at until a while after starting."""
    give_entity_objects(hass, "light.kitchen", kind=LightEntity)
    hass.states.async_set("light.kitchen", "off")
    await _automation(hass, to="On")

    repair = SpookRepair(hass)
    await repair.async_activate()

    hass.bus.async_fire("component_loaded", {"component": "light"})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=9))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, ISSUE) is None

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10, seconds=1))
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10, seconds=5))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, ISSUE)

    await repair.async_deactivate()
