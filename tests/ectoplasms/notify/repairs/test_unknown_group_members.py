"""Tests for the notify group unknown members repair."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.components.group.notify import GroupNotifyPlatform
from homeassistant.components.notify.legacy import NOTIFY_SERVICES

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.notify.repairs.unknown_group_members import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE_ID = "notify_unknown_group_members_everyone"


def _install_group(
    hass: HomeAssistant,
    members: list[dict[str, Any]],
    name: str = "everyone",
    integration: str = "group",
) -> GroupNotifyPlatform:
    """Register a legacy notify group the way Home Assistant does."""
    service = GroupNotifyPlatform(hass, members)
    service._service_name = name
    hass.data.setdefault(NOTIFY_SERVICES, {}).setdefault(integration, []).append(
        service
    )
    return service


async def test_unknown_member_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a notify group forwarding to a non-existing action is reported."""
    hass.services.async_register("notify", "still_here", lambda _call: None)
    _install_group(hass, [{"action": "still_here"}, {"action": "old_phone"}])

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)
    assert issue
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["group"] == "notify.everyone"

    # Only the missing one, named as the action it would have called.
    assert issue.translation_placeholders["members"] == "- `notify.old_phone`"


async def test_existing_members_are_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a notify group whose members all exist is left alone."""
    hass.services.async_register("notify", "phone", lambda _call: None)
    hass.services.async_register("notify", "tablet", lambda _call: None)
    _install_group(hass, [{"action": "phone"}, {"action": "tablet"}])

    await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


async def test_member_carrying_data_is_still_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a member with its own default data is checked like any other.

    A member may carry a `data:` block of per-target defaults. That changes
    the payload, not whether the action exists.
    """
    _install_group(hass, [{"action": "old_phone", "data": {"priority": "high"}}])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)


async def test_member_named_like_an_entity_is_still_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a member is checked as an action, never as an entity.

    A member is a bare action slug. Registering an entity by that name
    changes nothing: the group calls `notify.<slug>` and that action is what
    has to exist.
    """
    hass.states.async_set("notify.old_phone", "unknown")
    _install_group(hass, [{"action": "old_phone"}])

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)


async def test_non_group_notify_services_are_skipped(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a plain notify platform is never inspected.

    The false-positive twin. Every legacy notify platform lives in the same
    place, and only the group ones forward to other actions.
    """
    plain_platform = SimpleNamespace(
        entities=[{"action": "does_not_exist"}], _service_name="everyone"
    )
    hass.data.setdefault(NOTIFY_SERVICES, {})["telegram"] = [plain_platform]

    await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


async def test_group_registered_by_another_integration_is_found(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test groups are found by type, not by the key they are stored under."""
    _install_group(hass, [{"action": "old_phone"}], integration="somewhere_else")

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)


async def test_no_notify_services_does_nothing(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test nothing happens when no legacy notify platform is set up."""
    await SpookRepair(hass).async_inspect()

    assert not issue_registry.issues


async def test_issue_is_cleaned_up_when_the_member_returns(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes away once the notify action is registered again."""
    _install_group(hass, [{"action": "late_phone"}])
    repair = SpookRepair(hass)

    await repair._async_inspect_with_cleanup()
    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID)

    hass.services.async_register("notify", "late_phone", lambda _call: None)
    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, _ISSUE_ID) is None
