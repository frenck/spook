"""Tests for the script unknown state references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from homeassistant.components.cover import CoverEntity
from homeassistant.components.light import LightEntity
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.script.repairs.unknown_state_references import (
    SpookRepair,
)
from tests.entity_objects import give_entity_objects
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "script_unknown_state_references_script.haunted"


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
async def test_state_never_had_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a state the entity is never in is reported, with a guess."""
    give_entity_objects(hass, "cover.garage", kind=CoverEntity)
    hass.states.async_set("cover.garage", "open")
    await async_wait_recording_done(hass)
    await _script(hass, "{{ is_state('cover.garage', 'clossed') }}")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "script_unknown_state_references"
    assert issue.translation_placeholders == {
        "edit": "/config/script/edit/haunted",
        "entity_id": "script.haunted",
        "script": "Haunted",
        "states": "- `clossed` for `cover.garage` (did you mean `closed`?)",
    }


async def test_case_only_is_reported_without_a_recorder(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a difference in case alone is reported, recorder or not."""
    give_entity_objects(hass, "cover.garage", kind=CoverEntity)
    hass.states.async_set("cover.garage", "open")
    await _script(hass, "{{ 'cover.garage' is is_state('Closed') }}")

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["states"] == (
        "- `Closed` for `cover.garage` (did you mean `closed`?)"
    )


def _following(options: dict[str, Any], **target: Any) -> dict[str, Any]:
    """Return a script waiting on Spook's state trigger, to be On."""
    trigger: dict[str, Any] = {
        "trigger": "spook.state_changed",
        "options": {"to": ["On"], **options},
    }
    if target:
        trigger["target"] = target
    return {"sequence": [{"wait_for_trigger": [trigger]}]}


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        pytest.param(
            _following({"domain": ["light"]}),
            ["light.hall", "light.kitchen"],
            id="picked by domain",
        ),
        pytest.param(
            _following(
                {"exclude_target": {"entity_id": ["light.hall"]}},
                entity_id=["light.kitchen", "light.hall"],
            ),
            ["light.kitchen"],
            id="targeted, one left out",
        ),
    ],
)
async def test_spook_trigger_names_what_it_watches(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    config: dict[str, Any],
    expected: list[str],
) -> None:
    """Test Spook's own trigger names its states for exactly what it watches."""
    give_entity_objects(hass, "light.kitchen", "light.hall", kind=LightEntity)
    hass.states.async_set("light.kitchen", "off")
    hass.states.async_set("light.hall", "off")
    script = SimpleNamespace(
        entity_id="script.haunted",
        name="Haunted",
        unique_id="haunted",
        raw_config=config,
    )
    component = SimpleNamespace(
        entities=[script],
        get_entity=lambda entity_id: script if entity_id == script.entity_id else None,
    )
    hass.data[DATA_INSTANCES]["script"] = component

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["states"] == "\n".join(
        f"- `On` for `{entity_id}` (did you mean `on`?)" for entity_id in expected
    )
