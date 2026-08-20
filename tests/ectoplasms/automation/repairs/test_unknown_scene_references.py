"""Tests for scene references in automations.

Scenes were ignored wholesale, because `scene.create` builds them while an
automation runs and nothing knows about them beforehand. These pin the
narrower rule: a scene some configured action creates is known, any other
missing scene is reported.
"""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.setup import async_setup_component

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.automation.repairs.unknown_entity_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


async def _inspect(hass: HomeAssistant, actions: list[dict]) -> None:
    """Set up an automation with the given actions and inspect it."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            "automation": [
                {
                    "alias": "Scene test",
                    "triggers": [{"trigger": "event", "event_type": "poke"}],
                    "actions": actions,
                },
            ],
        },
    )
    await hass.async_block_till_done()
    await SpookRepair(hass)._async_inspect_with_cleanup()


def _reported(issue_registry: ir.IssueRegistry) -> str | None:
    """Return the reported entities for the test automation, if any."""
    issue = issue_registry.async_get_issue(
        DOMAIN, "automation_unknown_entity_references_automation.scene_test"
    )
    return issue.translation_placeholders["entities"] if issue else None


async def test_missing_scene_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene that does not exist is reported."""
    await _inspect(
        hass,
        [{"action": "scene.turn_on", "target": {"entity_id": "scene.deleted"}}],
    )

    assert "scene.deleted" in (_reported(issue_registry) or "")


async def test_existing_scene_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene that exists is left alone."""
    hass.states.async_set("scene.movie_night", "scening")

    await _inspect(
        hass,
        [{"action": "scene.turn_on", "target": {"entity_id": "scene.movie_night"}}],
    )

    assert _reported(issue_registry) is None


async def test_scene_created_by_an_action_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene the same automation creates is treated as known.

    This is the snapshot-then-restore pattern, and the reason scenes were
    ignored in the first place.
    """
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "action": "scene.create",
                "data": {"scene_id": "before", "snapshot_entities": ["light.hall"]},
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.before"}},
        ],
    )

    assert _reported(issue_registry) is None


async def test_scene_created_in_a_nested_block_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene.create inside a branch still counts."""
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "if": [
                    {"condition": "state", "entity_id": "light.hall", "state": "on"}
                ],
                "then": [
                    {
                        "action": "scene.create",
                        "data": {
                            "scene_id": "nested",
                            "snapshot_entities": ["light.hall"],
                        },
                    },
                ],
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.nested"}},
        ],
    )

    assert _reported(issue_registry) is None


async def test_templated_scene_id_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a templated scene_id does not silence the scene it names.

    Spook cannot know what the template renders to, so the safe answer is to
    keep reporting rather than assume a match.
    """
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "action": "scene.create",
                "data": {
                    "scene_id": "{{ 'dynamic' }}",
                    "snapshot_entities": ["light.hall"],
                },
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.dynamic"}},
        ],
    )

    assert "scene.dynamic" in (_reported(issue_registry) or "")
