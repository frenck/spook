"""Tests for the script unknown attribute references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.script.repairs.unknown_attribute_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "script_unknown_attribute_references_script.haunted"


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


async def _script(hass: HomeAssistant, template: str) -> None:
    """Set up a script whose only step is a template condition."""
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "haunted": {
                    "alias": "Haunted",
                    "sequence": [
                        {"condition": "template", "value_template": template},
                    ],
                }
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_never_had_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute the entity never had is reported, with a guess."""
    hass.states.async_set("sensor.outside", "12", {"humidity": 80})
    await async_wait_recording_done(hass)
    await _script(hass, "{{ state_attr('sensor.outside', 'humidty') > 50 }}")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "script_unknown_attribute_references"
    assert issue.translation_placeholders == {
        "attributes": "- `humidty` of `sensor.outside` (did you mean `humidity`?)",
        "edit": "/config/script/edit/haunted",
        "entity_id": "script.haunted",
        "script": "Haunted",
    }


@pytest.mark.usefixtures("recorder_mock")
async def test_attribute_only_in_history_is_fine(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an attribute the entity had once, and not right now, is fine."""
    hass.states.async_set("sensor.outside", "12", {"humidity": 80})
    hass.states.async_set("sensor.outside", "unavailable", {})
    await async_wait_recording_done(hass)
    await _script(hass, "{{ state_attr('sensor.outside', 'humidity') > 50 }}")

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_case_only_is_reported_without_a_recorder(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a difference in case alone is reported, recorder or not."""
    hass.states.async_set("sensor.outside", "12", {"humidity": 80})
    await _script(hass, "{{ state_attr('sensor.outside', 'Humidity') > 50 }}")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["attributes"] == (
        "- `Humidity` of `sensor.outside` (did you mean `humidity`?)"
    )
