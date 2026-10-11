"""Tests for the automation removed users repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook.draft_checking import async_check_draft
from custom_components.spook.ectoplasms.automation.repairs.unknown_user_references import (
    SpookRepair,
)
import pytest
from tests.repair_helpers import async_issue_about, async_removed_user_id

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "automation_unknown_user_references_automation.haunted"

BOO = {"trigger": "event", "event_type": "boo"}


def _waiting_for(*user_ids: str, **trigger: Any) -> dict[str, Any]:
    """Return an event trigger waiting for an event by these users."""
    users = user_ids[0] if len(user_ids) == 1 else list(user_ids)
    return {**BOO, "context": {"user_id": users}, **trigger}


def _when(template: str) -> dict[str, Any]:
    """Return a template condition."""
    return {"condition": "template", "value_template": template}


async def _reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    triggers: Any,
    *,
    conditions: list[Any] | None = None,
    actions: list[Any] | None = None,
    **extra: Any,
) -> str | None:
    """Set up the haunted automation, inspect it, and return the users reported."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": triggers,
                    "conditions": conditions or [],
                    "actions": actions or [],
                    **extra,
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("automation.haunted").state == "on"

    await SpookRepair(hass).async_inspect()

    if (issue := async_issue_about(issue_registry, ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["users"]


async def test_an_event_trigger_waiting_for_a_removed_user_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an event trigger waiting for a removed user is reported."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(hass, issue_registry, [_waiting_for(removed)])
        == f"- `{removed}`"
    )

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "automation_unknown_user_references"
    assert issue.translation_placeholders == {
        "automation": "Haunted",
        "edit": "/config/automation/edit/haunted",
        "entity_id": "automation.haunted",
        "users": f"- `{removed}`",
    }
    assert issue.learn_more_url == "https://spook.boo/automation#removed-users"


async def test_users_that_exist_are_not_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test only the removed user of a list is reported.

    The system users Home Assistant makes itself are users too.
    """
    removed = await async_removed_user_id(hass)
    person = await hass.auth.async_create_user("Frenck")
    system = await hass.auth.async_create_system_user("Supervisor")

    assert (
        await _reported(
            hass,
            issue_registry,
            [_waiting_for(person.id, removed, system.id)],
            conditions=[_when(f"{{{{ context.user_id != '{system.id}' }}}}")],
        )
        == f"- `{removed}`"
    )


async def test_existing_users_alone_are_clean(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an automation naming only users that exist is not reported."""
    await async_removed_user_id(hass)
    person = await hass.auth.async_create_user("Frenck")
    system = await hass.auth.async_create_system_user("Supervisor")

    assert (
        await _reported(
            hass,
            issue_registry,
            [_waiting_for(person.id, system.id)],
            conditions=[_when(f"{{{{ context.user_id == '{person.id}' }}}}")],
        )
        is None
    )


async def test_a_wait_for_a_removed_user_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an event trigger the actions wait for is read too."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass,
            issue_registry,
            [BOO],
            actions=[{"wait_for_trigger": [_waiting_for(removed)]}],
        )
        == f"- `{removed}`"
    )


@pytest.mark.parametrize(
    "template",
    [
        "{{ trigger.to_state.context.user_id == 'USER' }}",
        "{{ trigger.from_state.context.user_id == 'USER' }}",
        "{{ trigger.zone.context.user_id == 'USER' }}",
        "{{ 'USER' == trigger.event.context.user_id }}",
        "{{ trigger.event.context.user_id in ['USER'] }}",
        "{{ trigger['to_state'].context['user_id'] != 'USER' }}",
        "{{ context.user_id == 'USER' }}",
        "{{ this.context.user_id == 'USER' }}",
        "{{ wait.trigger.event.context.user_id == 'USER' }}",
        "{{ wait.trigger.to_state.context.user_id == 'USER' }}",
        "{{ states.light.kitchen.context.user_id == 'USER' }}",
        "{{ states['light.kitchen'].context.user_id == 'USER' }}",
        "{{ states['light']['kitchen'].context.user_id == 'USER' }}",
        "{{ state_attr('person.casper', 'user_id') == 'USER' }}",
        "{{ states.person.casper.attributes.user_id == 'USER' }}",
        "{{ is_state_attr('person.casper', 'user_id', 'USER') }}",
        "{% if context.user_id == 'USER' and true %}yes{% endif %}",
    ],
)
async def test_templates_comparing_a_user_id_are_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test a template comparing the ID of a user with a removed one is reported."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass,
            issue_registry,
            [BOO],
            conditions=[_when(template.replace("USER", removed))],
        )
        == f"- `{removed}`"
    )


@pytest.mark.parametrize(
    ("template", "extra"),
    [
        pytest.param("{{ trigger.event.data.user_id == 'USER' }}", {}, id="event-data"),
        pytest.param(
            "{{ trigger.event.data.context.user_id == 'USER' }}",
            {},
            id="context-in-event-data",
        ),
        pytest.param(
            "{{ wait.trigger.event.data.context.user_id == 'USER' }}",
            {},
            id="context-in-waited-event-data",
        ),
        pytest.param(
            "{{ states.sensor.casper.attributes.context.user_id == 'USER' }}",
            {},
            id="context-in-attributes",
        ),
        pytest.param(
            "{{ states['sensor.casper'].attributes.context.user_id == 'USER' }}",
            {},
            id="context-in-attributes-by-entity-id",
        ),
        pytest.param(
            "{{ trigger.to_state.attributes.context.user_id == 'USER' }}",
            {},
            id="context-in-trigger-attributes",
        ),
        pytest.param(
            "{{ this.attributes.context.user_id == 'USER' }}",
            {},
            id="context-in-own-attributes",
        ),
        pytest.param(
            "{{ trigger.context.user_id == 'USER' }}", {}, id="trigger-has-no-context"
        ),
        pytest.param(
            "{{ context.parent.user_id == 'USER' }}", {}, id="deeper-in-the-context"
        ),
        pytest.param(
            "{{ state_attr('sensor.casper', 'user_id') == 'USER' }}",
            {},
            id="not-a-person",
        ),
        pytest.param("{{ context.user_id | lower == 'USER' }}", {}, id="filtered"),
        pytest.param("{{ 'USER' }}", {}, id="not-compared"),
        pytest.param(
            "{{ context.user_id == 'USER' ~ 'x' }}", {}, id="compared-to-more"
        ),
        pytest.param("{{ ghost.context.user_id == 'USER' }}", {}, id="something-else"),
        pytest.param(
            "{{ ghost.is_state_attr('person.casper', 'user_id', 'USER') }}",
            {},
            id="a-method",
        ),
        pytest.param(
            "{{ is_state_attr('sensor.casper', 'user_id', 'USER') }}",
            {},
            id="not-a-person-test",
        ),
        pytest.param(
            "{{ is_state_attr('person.casper', 'user_id', 'USER') }}",
            {"variables": {"is_state_attr": "x"}},
            id="a-variable-by-that-name",
        ),
        pytest.param(
            "{% set context = {'user_id': 'x'} %}{{ context.user_id == 'USER' }}",
            {},
            id="set-in-the-template",
        ),
        pytest.param(
            "{{ context.user_id == 'USER' }}",
            {"variables": {"context": {"user_id": "x"}}},
            id="variable",
        ),
        pytest.param("{{ context.user_id == 'casper' }}", {}, id="not-a-user-id"),
    ],
)
async def test_what_is_not_a_user_id_comparison_is_not_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    template: str,
    extra: dict[str, Any],
) -> None:
    """Test a removed user is left alone where nothing compares it with a user.

    What an event calls `user_id` is up to whoever fires it, and only a
    person promises its `user_id` is a user.
    """
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass,
            issue_registry,
            [BOO],
            conditions=[_when(template.replace("USER", removed))],
            **extra,
        )
        is None
    )


async def test_event_data_of_an_event_trigger_is_not_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test `user_id` in the event data is not taken for a user."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass, issue_registry, [{**BOO, "event_data": {"user_id": removed}}]
        )
        is None
    )


async def test_data_handed_to_an_action_is_not_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test what is handed to an action is not taken for a trigger of its own."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass,
            issue_registry,
            [BOO],
            actions=[
                {
                    "action": "script.turn_on",
                    "target": {"entity_id": "script.casper"},
                    "data": {"variables": _waiting_for(removed)},
                }
            ],
        )
        is None
    )


async def test_disabled_and_never_rendered_parts_are_not_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a disabled trigger or step, and a description, are left alone."""
    removed = await async_removed_user_id(hass)

    assert (
        await _reported(
            hass,
            issue_registry,
            [BOO, _waiting_for(removed, enabled=False)],
            conditions=[
                {**_when(f"{{{{ context.user_id == '{removed}' }}}}"), "enabled": False}
            ],
            description=f"Ignores {{{{ context.user_id == '{removed}' }}}}",
        )
        is None
    )


async def test_removing_a_user_is_noticed(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test removing a user the automation names raises the issue."""
    await hass.auth.async_create_user("Owner")
    user = await hass.auth.async_create_user("Casper")
    assert await _reported(hass, issue_registry, [_waiting_for(user.id)]) is None

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
    """Test a draft automation naming a removed user is caught before saving."""
    removed = await async_removed_user_id(hass)

    found = await async_check_draft(
        hass,
        "automation",
        {
            "triggers": [_waiting_for(removed)],
            "actions": [{"event": "boo"}],
        },
    )

    assert found == {"users": [removed]}


async def test_a_draft_with_a_mapping_for_a_user_is_still_checked(
    hass: HomeAssistant,
) -> None:
    """Test a context user that cannot be one does not stop a draft check.

    Only the actions of a draft are validated, so a trigger can hold anything.
    """
    removed = await async_removed_user_id(hass)

    found = await async_check_draft(
        hass,
        "automation",
        {
            "triggers": [
                {**BOO, "context": {"user_id": {"boo": removed}}},
                {**BOO, "context": {"user_id": [removed, {"boo": removed}]}},
            ],
            "actions": [{"event": "boo"}],
        },
    )

    assert found == {"users": [removed]}
