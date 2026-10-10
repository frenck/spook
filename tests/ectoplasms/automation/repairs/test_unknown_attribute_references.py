"""Tests for the automation unknown attribute references repair."""

# pylint: disable=wrong-import-order,protected-access
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook import attribute_checking
from custom_components.spook.ectoplasms.automation.repairs.unknown_attribute_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "automation_unknown_attribute_references_automation.haunted"


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


async def _automation(hass: HomeAssistant, attribute: str, **extra: Any) -> None:
    """Set up an automation triggering on an attribute of the kitchen light."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": [
                        {
                            "trigger": "state",
                            "entity_id": "light.kitchen",
                            "attribute": attribute,
                            **extra,
                        }
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
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    await _automation(hass, "Brightness")

    repair = SpookRepair(hass)
    await repair.async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "automation_unknown_attribute_references"
    assert issue.translation_placeholders == {
        "attributes": (
            "- `Brightness` of `light.kitchen` (did you mean `brightness`?)"
        ),
        "automation": "Haunted",
        "edit": "/config/automation/edit/haunted",
        "entity_id": "automation.haunted",
    }


async def test_without_a_recorder_only_case_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute nobody can rule out is not reported without history."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    await _automation(hass, "wobble")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_never_had_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute the entity never had is reported, from history."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255, "glow": 1})
    await async_wait_recording_done(hass)
    await _automation(hass, "wobble")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == (
        "- `wobble` of `light.kitchen`"
    )


@pytest.mark.usefixtures("recorder_mock")
async def test_custom_attribute_present_now_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an attribute an integration adds of its own is fine while there.

    Even when the recorder has never seen it, which is what it says here.
    """

    def _never_seen_it(_hass: HomeAssistant, entity_ids: list[str]) -> dict:
        return {entity_id: ({"brightness"}, True) for entity_id in entity_ids}

    monkeypatch.setattr(
        attribute_checking, "_read_recorded_attribute_keys", _never_seen_it
    )
    hass.states.async_set("light.kitchen", "on", {"wobble": 1})
    await _automation(hass, "wobble")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_only_in_history_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute the entity had once, and not right now, is fine."""
    hass.states.async_set("light.kitchen", "on", {"wobble": 1})
    hass.states.async_set("light.kitchen", "off", {})
    await async_wait_recording_done(hass)
    await _automation(hass, "wobble")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_fixed_is_cleared(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes once the attribute is spelled the way it is."""
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    await _automation(hass, "Brightness")

    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, ISSUE)

    hass.states.async_set("light.kitchen", "on", {"brightness": 255, "Brightness": 1})
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    assert async_issue_about(issue_registry, ISSUE) is None


async def test_not_before_the_recorder_settles(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test nothing is looked at until a while after starting.

    Not even when something that would normally make it look happens.
    """
    hass.states.async_set("light.kitchen", "on", {"brightness": 255})
    await _automation(hass, "Brightness")

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
