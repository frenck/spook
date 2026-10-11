"""Tests for the script removed users repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook.draft_checking import async_check_draft
from custom_components.spook.ectoplasms.script.repairs.unknown_user_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about, async_removed_user_id

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "script_unknown_user_references_script.haunted"


def _only_for(user_id: str) -> dict[str, Any]:
    """Return a condition step that only lets this user through."""
    return {
        "condition": "template",
        "value_template": f"{{{{ context.user_id == '{user_id}' }}}}",
    }


async def _reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, **script: Any
) -> str | None:
    """Set up the haunted script, inspect it, and return the users reported."""
    assert await async_setup_component(
        hass, "script", {"script": {"haunted": {"alias": "Haunted", **script}}}
    )
    await hass.async_block_till_done()
    assert hass.states.get("script.haunted").state == "off"

    await SpookRepair(hass).async_inspect()

    if (issue := async_issue_about(issue_registry, ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["users"]


async def test_a_removed_user_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a script checking who started it against a removed user is reported."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(hass, issue_registry, sequence=[_only_for(removed)])
        == f"- `{removed}`"
    )

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "script_unknown_user_references"
    assert issue.translation_placeholders == {
        "script": "Haunted",
        "edit": "/config/script/edit/haunted",
        "entity_id": "script.haunted",
        "users": f"- `{removed}`",
    }
    assert issue.learn_more_url == "https://spook.boo/script#removed-users"


async def test_users_that_exist_are_not_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a script naming a user, and a system user, that exist is clean."""
    await async_removed_user_id(hass)
    person = await hass.auth.async_create_user("Frenck")
    system = await hass.auth.async_create_system_user("Supervisor")

    assert (
        await _reported(
            hass,
            issue_registry,
            sequence=[_only_for(person.id), _only_for(system.id)],
        )
        is None
    )


async def test_a_wait_for_a_removed_user_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an event trigger the script waits for is read too."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass,
            issue_registry,
            sequence=[
                {
                    "wait_for_trigger": [
                        {
                            "trigger": "event",
                            "event_type": "boo",
                            "context": {"user_id": [removed]},
                        }
                    ]
                }
            ],
        )
        == f"- `{removed}`"
    )


async def test_a_field_called_context_is_not_the_user(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a script handed a `context` of its own is not read.

    A field is handed to every template under its name.
    """
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass,
            issue_registry,
            fields={"context": {"selector": {"object": {}}}},
            sequence=[_only_for(removed)],
        )
        is None
    )


async def test_a_disabled_step_is_not_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a removed user only a disabled step names is left alone."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass, issue_registry, sequence=[{**_only_for(removed), "enabled": False}]
        )
        is None
    )


async def test_removing_a_user_is_noticed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test removing a user the script names raises the issue."""
    await hass.auth.async_create_user("Owner")
    user = await hass.auth.async_create_user("Casper")
    assert await _reported(hass, issue_registry, sequence=[_only_for(user.id)]) is None

    repair = SpookRepair(hass)
    await repair.async_activate()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, ISSUE) is None

    await hass.auth.async_remove_user(user)
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert async_issue_about(issue_registry, ISSUE)

    await repair.async_deactivate()


async def test_a_draft_names_the_removed_users(hass: HomeAssistant) -> None:
    """Test a draft script naming a removed user is caught before saving."""
    removed = await async_removed_user_id(hass)

    found = await async_check_draft(hass, "script", {"sequence": [_only_for(removed)]})

    assert found == {"users": [removed]}
