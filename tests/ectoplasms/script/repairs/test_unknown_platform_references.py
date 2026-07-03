"""Tests for the script unknown trigger and condition references repairs."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.script.repairs import (
    unknown_condition_references,
    unknown_trigger_references,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def test_broken_scripts_get_specific_issues(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test scripts with unavailable trigger or condition types are named.

    Scripts using triggers (via ``wait_for_trigger``) or conditions from
    removed integrations fail validation and become unavailable; the
    repairs must inspect them anyway and name the offending keys.
    """
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "haunted_wait": {
                    "sequence": [
                        {
                            "wait_for_trigger": [
                                {"trigger": "ghost_integration.appeared"},
                            ],
                        },
                    ],
                },
                "haunted_check": {
                    "sequence": [
                        {"condition": "ghost_integration.is_haunted"},
                        {"action": "light.turn_on"},
                    ],
                },
                "healthy": {
                    "sequence": [
                        {
                            "condition": "state",
                            "entity_id": "sun.sun",
                            "state": "above_horizon",
                        },
                        {"action": "light.turn_on"},
                    ],
                },
            },
        },
    )
    await hass.async_block_till_done()

    # Both broken scripts failed validation and are unavailable.
    for object_id in ("haunted_wait", "haunted_check"):
        state = hass.states.get(f"script.{object_id}")
        assert state
        assert state.state == "unavailable"

    trigger_repair = unknown_trigger_references.SpookRepair(hass)
    await trigger_repair.async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "script_unknown_trigger_references_script.haunted_wait",
    )
    assert issue
    assert issue.translation_placeholders
    assert (
        issue.translation_placeholders["triggers"] == "- `ghost_integration.appeared`"
    )

    condition_repair = unknown_condition_references.SpookRepair(hass)
    await condition_repair.async_inspect()

    issue = issue_registry.async_get_issue(
        DOMAIN,
        "script_unknown_condition_references_script.haunted_check",
    )
    assert issue
    assert issue.translation_placeholders
    assert (
        issue.translation_placeholders["conditions"]
        == "- `ghost_integration.is_haunted`"
    )

    for repair_name in (
        "script_unknown_trigger_references",
        "script_unknown_condition_references",
    ):
        assert (
            issue_registry.async_get_issue(
                DOMAIN,
                f"{repair_name}_script.healthy",
            )
            is None
        )
