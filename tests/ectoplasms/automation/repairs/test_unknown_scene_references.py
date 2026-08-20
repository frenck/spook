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

from homeassistant.components import automation, script
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


async def test_scene_created_with_legacy_data_template_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the legacy `data_template` form is read too.

    Raw configuration has not had `data_template` folded into `data` yet, and
    Home Assistant still accepts it, so a scene created that way has to count.
    """
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "service": "scene.create",
                "data_template": {
                    "scene_id": "legacy",
                    "snapshot_entities": ["light.hall"],
                },
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.legacy"}},
        ],
    )

    assert _reported(issue_registry) is None


async def test_scene_created_by_a_script_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a scene a script creates counts for an automation that uses it.

    Scripts are scanned as well as automations, because the snapshot and the
    restore do not have to live in the same place.
    """
    hass.states.async_set("light.hall", "on")

    assert await async_setup_component(
        hass,
        script.DOMAIN,
        {
            "script": {
                "snapshotter": {
                    "sequence": [
                        {
                            "action": "scene.create",
                            "data": {
                                "scene_id": "from_script",
                                "snapshot_entities": ["light.hall"],
                            },
                        },
                    ],
                },
            },
        },
    )
    await hass.async_block_till_done()

    await _inspect(
        hass,
        [{"action": "scene.turn_on", "target": {"entity_id": "scene.from_script"}}],
    )

    assert _reported(issue_registry) is None


async def test_scene_id_in_either_payload_key_counts(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test both payload keys are read, not just whichever comes first.

    A step can carry `data` and `data_template` at once, with the scene_id in
    either. Home Assistant merges them, so preferring one key loses the other.
    """
    hass.states.async_set("light.hall", "on")

    await _inspect(
        hass,
        [
            {
                "service": "scene.create",
                "data": {"snapshot_entities": ["light.hall"]},
                "data_template": {"scene_id": "split"},
            },
            {"action": "scene.turn_on", "target": {"entity_id": "scene.split"}},
        ],
    )

    assert _reported(issue_registry) is None


async def test_scene_created_by_a_broken_automation_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a configuration Home Assistant rejected does not vouch for a scene.

    Home Assistant keeps a placeholder entity for an automation it could not
    validate, and that placeholder still carries the raw configuration. It can
    never run, so the scene it would have created does not exist.
    """
    hass.states.async_set("light.hall", "on")

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            "automation": [
                {
                    # No triggers key, so validation fails and Home Assistant
                    # keeps an unavailable placeholder for it.
                    "alias": "Broken",
                    "actions": [
                        {
                            "action": "scene.create",
                            "data": {
                                "scene_id": "never_made",
                                "snapshot_entities": ["light.hall"],
                            },
                        },
                    ],
                },
                {
                    "alias": "Scene test",
                    "triggers": [{"trigger": "event", "event_type": "poke"}],
                    "actions": [
                        {
                            "action": "scene.turn_on",
                            "target": {"entity_id": "scene.never_made"},
                        },
                    ],
                },
            ],
        },
    )
    await hass.async_block_till_done()

    await SpookRepair(hass)._async_inspect_with_cleanup()

    assert "scene.never_made" in (_reported(issue_registry) or "")
