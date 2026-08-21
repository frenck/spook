"""Tests for action names reaching the entity reference check.

An action name has the same shape as an entity ID. A legacy notify group is
the common case: `notify.my_phone` is an action rather than an entity, and it
arrives at the entity check through two different doors. Neither should
produce a repair.
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
                    "alias": "Notify router",
                    "triggers": [{"trigger": "event", "event_type": "doorbell"}],
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
        DOMAIN, "automation_unknown_entity_references_automation.notify_router"
    )
    return issue.translation_placeholders["entities"] if issue else None


async def test_legacy_target_in_service_data_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a legacy notify group used as a target is left alone.

    Home Assistant reads `data.entity_id` as a target and hands the name back
    as a referenced entity, so this one does not even originate in Spook.
    """
    hass.services.async_register("notify", "my_phone", lambda _c: None)

    await _inspect(
        hass,
        [
            {
                "service": "notify.notify",
                "data": {"message": "Doorbell", "entity_id": "notify.my_phone"},
            },
        ],
    )

    assert _reported(issue_registry) is None


async def test_notify_group_in_a_target_block_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a legacy notify group named in a target block is left alone."""
    hass.services.async_register("notify", "all_phones", lambda _c: None)

    await _inspect(
        hass,
        [
            {
                "action": "notify.send_message",
                "target": {"entity_id": "notify.all_phones"},
                "data": {"message": "Doorbell"},
            },
        ],
    )

    assert _reported(issue_registry) is None


async def test_third_party_fan_out_payload_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test notifier names in a third-party action's payload are left alone.

    A fan-out action takes a list of notifier names under a key of its own
    choosing. Home Assistant sees nothing here; this arrives purely through
    Spook scanning the payload.
    """
    hass.services.async_register("notify", "mobile_app_phone", lambda _c: None)
    hass.services.async_register("notify", "old_tablet", lambda _c: None)

    await _inspect(
        hass,
        [
            {
                "action": "notifier_hub.send",
                "data": {
                    "title": "Hello",
                    "message": "World",
                    "notify": ["notify.mobile_app_phone", "notify.old_tablet"],
                },
            },
        ],
    )

    assert _reported(issue_registry) is None


async def test_a_removed_entity_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the check still does its job alongside a notify group.

    The point is dropping action names, not going quiet. A genuinely missing
    entity in the same automation has to survive.
    """
    hass.services.async_register("notify", "my_phone", lambda _c: None)

    await _inspect(
        hass,
        [
            {
                "action": "notify.send_message",
                "target": {"entity_id": "notify.my_phone"},
            },
            {"action": "light.turn_on", "target": {"entity_id": "light.removed"}},
        ],
    )

    reported = _reported(issue_registry) or ""
    assert "light.removed" in reported
    assert "notify.my_phone" not in reported


async def test_a_removed_script_is_still_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test an entity ID that doubles as an action name is not lost.

    A script owns both `script.x` as an entity and `script.x` as an action, so
    they appear and disappear together. Deleting one does not leave the other
    behind to vouch for it.
    """
    hass.services.async_register("script", "turn_on", lambda _c: None)

    await _inspect(
        hass,
        [{"action": "script.turn_on", "target": {"entity_id": "script.removed"}}],
    )

    assert "script.removed" in (_reported(issue_registry) or "")
