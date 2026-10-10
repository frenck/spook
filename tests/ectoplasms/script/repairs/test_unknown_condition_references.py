"""Tests for the script unknown condition references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.script.repairs.unknown_condition_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def test_a_condition_key_in_repeat_items_is_no_condition(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a `condition` key in the items a repeat goes over is left alone.

    The items are data, handed to the steps as `repeat.item`. A field of
    them called `condition` is somebody's own, not a condition. A real
    condition next to them is still read.
    """
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "weather_scene": {
                    "sequence": [
                        {
                            "repeat": {
                                "for_each": [
                                    {"condition": "rainy", "scene": "scene.cosy"},
                                    {"condition": "sunny", "scene": "scene.bright"},
                                ],
                                "sequence": [
                                    {
                                        "condition": "ghost_integration.is_haunted",
                                    }
                                ],
                            }
                        }
                    ]
                }
            }
        },
    )
    await hass.async_block_till_done()

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(
        issue_registry, "script_unknown_condition_references_script.weather_scene"
    )
    assert issue
    assert issue.translation_placeholders
    assert (
        issue.translation_placeholders["conditions"]
        == "- `ghost_integration.is_haunted`"
    )
