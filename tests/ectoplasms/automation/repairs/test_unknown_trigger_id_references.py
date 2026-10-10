"""Tests for the automation unknown trigger ID references repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.setup import async_setup_component

from custom_components.spook import draft_checking
from custom_components.spook.ectoplasms.automation.repairs.unknown_trigger_id_references import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "automation_unknown_trigger_id_references_automation.haunted"

ARRIVED = {"trigger": "event", "event_type": "arrived", "id": "arrived"}
LEFT = {"trigger": "event", "event_type": "left", "id": "left"}
NO_ID = {"trigger": "event", "event_type": "nameless"}


def _checking(*ids: Any) -> dict[str, Any]:
    """Return a trigger condition checking for these IDs."""
    return {"condition": "trigger", "id": ids[0] if len(ids) == 1 else list(ids)}


def _when(template: str) -> dict[str, Any]:
    """Return a condition step with a template."""
    return {"condition": "template", "value_template": template}


async def _unknown(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    triggers: Any,
    *,
    conditions: list[Any] | None = None,
    actions: list[Any] | None = None,
    **extra: Any,
) -> set[str] | None:
    """Set up the haunted automation, inspect it, and return what is reported.

    `None` when there is no issue at all, so a test tells "nothing found"
    apart from an issue that found nothing.
    """
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
    return {
        line.removeprefix("- `").removesuffix("`")
        for line in issue.translation_placeholders["trigger_ids"].splitlines()
    }


async def test_unknown_id_in_a_trigger_condition_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a trigger condition asking for an ID no trigger has is reported."""
    assert await _unknown(
        hass,
        issue_registry,
        [ARRIVED, LEFT],
        conditions=[_checking("arived")],
        actions=[{"if": [_checking("left")], "then": []}],
    ) == {"arived"}

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "automation_unknown_trigger_id_references"
    assert issue.translation_placeholders == {
        "automation": "Haunted",
        "edit": "/config/automation/edit/haunted",
        "entity_id": "automation.haunted",
        "trigger_ids": "- `arived`",
    }
    assert issue.learn_more_url == (
        "https://spook.boo/automation#unknown-referenced-trigger-ids"
    )


async def test_known_ids_are_not_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an automation checking only for its own trigger IDs is clean."""
    assert (
        await _unknown(
            hass,
            issue_registry,
            [ARRIVED, LEFT],
            conditions=[_checking("arrived", "left")],
        )
        is None
    )


async def test_a_trigger_without_an_id_goes_by_its_position(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a trigger without an ID is known by its position, from `0`.

    Home Assistant reads the condition's IDs as text, so `1` written as a
    number is `"1"` too.
    """
    assert await _unknown(
        hass,
        issue_registry,
        [ARRIVED, NO_ID],
        conditions=[_checking("1", 1, "0", "2")],
    ) == {"0", "2"}


async def test_grouped_triggers_are_counted_flattened(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test triggers grouped under `triggers:` count as if they were listed.

    The trigger after a group of two is the third, `2`, not the second.
    """
    assert await _unknown(
        hass,
        issue_registry,
        [{"triggers": [ARRIVED, LEFT]}, NO_ID],
        conditions=[_checking("arrived", "left", "1", "2")],
    ) == {"1"}


async def test_old_style_triggers_are_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test triggers under `trigger:` with `platform:` are read the same."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "trigger": {"platform": "event", "event_type": "x", "id": "x"},
                    "condition": [_checking("x")],
                    "action": [{"if": [_checking("y")], "then": []}],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders["trigger_ids"] == "- `y`"


async def test_a_list_of_ids_reports_only_the_unknown_ones(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test each ID of a list is checked on its own."""
    assert await _unknown(
        hass,
        issue_registry,
        [ARRIVED, LEFT],
        conditions=[_checking("arrived", "ghost", "left", "spirit")],
    ) == {"ghost", "spirit"}


async def test_trigger_conditions_are_found_wherever_they_nest(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test trigger conditions in every kind of step and condition are read."""
    assert await _unknown(
        hass,
        issue_registry,
        [ARRIVED],
        conditions=[
            {"condition": "or", "conditions": [_checking("in_or")]},
            {"not": [_checking("in_not")]},
        ],
        actions=[
            _checking("as_a_step"),
            {"choose": [{"conditions": [_checking("in_choose")], "sequence": []}]},
            {"if": {"and": [_checking("in_if_and")]}, "then": []},
            {
                "repeat": {
                    "while": [_checking("in_while")],
                    "sequence": [
                        {
                            "repeat": {
                                "until": [_checking("in_until")],
                                "sequence": [],
                            }
                        }
                    ],
                }
            },
            {"parallel": [{"sequence": [_checking("in_parallel")]}]},
            {"sequence": [_checking("in_sequence")]},
        ],
    ) == {
        "as_a_step",
        "in_choose",
        "in_if_and",
        "in_not",
        "in_or",
        "in_parallel",
        "in_sequence",
        "in_until",
        "in_while",
    }


async def test_a_disabled_trigger_keeps_its_id_and_its_position(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a parked trigger is no unknown one, and still takes a position.

    Home Assistant counts the positions before it skips disabled triggers,
    so the trigger after a disabled one without an ID is still `1`.
    """
    assert (
        await _unknown(
            hass,
            issue_registry,
            [{**NO_ID, "enabled": False}, NO_ID, {**LEFT, "enabled": False}],
            conditions=[_checking("0", "1", "left")],
        )
        is None
    )


async def test_a_disabled_condition_is_left_out(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a parked trigger condition checks nothing, so is not reported."""
    assert (
        await _unknown(
            hass,
            issue_registry,
            [ARRIVED],
            conditions=[{**_checking("ghost"), "enabled": False}],
            actions=[{**_checking("spirit"), "enabled": False}],
        )
        is None
    )


async def test_a_trigger_condition_in_payload_is_left_out(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test something shaped like a trigger condition in event data is data."""
    assert (
        await _unknown(
            hass,
            issue_registry,
            [ARRIVED],
            actions=[{"event": "boo", "event_data": {"check": _checking("ghost")}}],
        )
        is None
    )


async def test_templates_comparing_the_trigger_id_are_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test `trigger.id` compared to text, in every way it is read."""
    assert await _unknown(
        hass,
        issue_registry,
        [ARRIVED],
        conditions=[
            _when("{{ trigger.id == 'equal' }}"),
            "{{ trigger.id != 'not_equal' }}",
        ],
        actions=[
            _when("{{ trigger.id in ['arrived', 'listed'] }}"),
            _when("{{ trigger.id not in ('arrived', 'tupled') }}"),
            _when("{{ 'reversed' == trigger.id }}"),
            _when("{{ trigger['id'] == 'bracketed' }}"),
            {"if": "{% if trigger.id == 'in_if' %}true{% endif %}", "then": []},
            {"event": "boo", "event_data": {"x": "{{ trigger.id == 'in_data' }}"}},
        ],
    ) == {
        "bracketed",
        "equal",
        "in_data",
        "in_if",
        "listed",
        "not_equal",
        "reversed",
        "tupled",
    }


@pytest.mark.parametrize(
    "template",
    [
        "{{ trigger.id | lower == 'ghost' }}",
        "{{ trigger.id == 'ghost' ~ 'ly' }}",
        "{{ 'ghost' in trigger.id }}",
        "{{ trigger.id == my_id }}",
        "{{ trigger.idx == 'ghost' }}",
        "{{ trigger.id.startswith('ghost') }}",
        "{{ trigger.id in ('ghost') }}",
    ],
)
async def test_computed_comparisons_are_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, template: str
) -> None:
    """Test a comparison something else takes part in is not read."""
    assert (
        await _unknown(
            hass,
            issue_registry,
            [ARRIVED],
            conditions=[_when(template)],
            variables={"my_id": "ghost"},
        )
        is None
    )


async def test_the_trigger_a_wait_ended_on_is_another_one(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test `wait.trigger.id` is not the trigger that started the automation."""
    assert (
        await _unknown(
            hass,
            issue_registry,
            [ARRIVED],
            actions=[
                {
                    "wait_for_trigger": [
                        {"trigger": "event", "event_type": "x", "id": "waited"}
                    ]
                },
                _when("{{ wait.trigger.id == 'waited' }}"),
            ],
        )
        is None
    )


async def test_a_template_with_its_own_trigger_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a template that sets `trigger` itself is not about the real one."""
    assert (
        await _unknown(
            hass,
            issue_registry,
            [ARRIVED],
            conditions=[
                _when("{% set trigger = {'id': 'ghost'} %}{{ trigger.id == 'ghost' }}")
            ],
        )
        is None
    )


@pytest.mark.parametrize(
    ("extra", "actions"),
    [
        ({"variables": {"trigger": {"id": "ghost"}}}, []),
        ({"trigger_variables": {"trigger": "ghost"}}, []),
        ({}, [{"variables": {"trigger": {"id": "ghost"}}}]),
        (
            {},
            [
                {
                    "action": "automation.trigger",
                    "target": {"entity_id": "automation.nothing"},
                    "response_variable": "trigger",
                }
            ],
        ),
    ],
)
async def test_an_automation_with_its_own_trigger_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    extra: dict[str, Any],
    actions: list[dict[str, Any]],
) -> None:
    """Test a variable called `trigger` replaces the real one, and is skipped.

    For the trigger conditions as much as for the templates: Home Assistant
    hands the conditions the variables too.
    """
    assert (
        await _unknown(
            hass,
            issue_registry,
            [ARRIVED],
            conditions=[_checking("ghost"), _when("{{ trigger.id == 'ghost' }}")],
            actions=actions,
            **extra,
        )
        is None
    )


async def test_templates_in_triggers_are_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a template in a trigger has no trigger to compare yet."""
    assert (
        await _unknown(
            hass,
            issue_registry,
            [{"trigger": "template", "value_template": "{{ trigger.id == 'x' }}"}],
        )
        is None
    )


async def test_an_id_that_looks_like_a_template_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an ID somebody most likely meant to be filled in is not reported."""
    assert (
        await _unknown(
            hass,
            issue_registry,
            [ARRIVED],
            conditions=[_checking("{{ which }}")],
        )
        is None
    )


async def test_an_automation_that_failed_to_load_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a broken automation is not reported: none of its triggers run."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "triggers": [{"trigger": "no_such_platform", "id": "x"}],
                    "conditions": [_checking("ghost")],
                    "actions": [],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("automation.haunted").state == "unavailable"

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_an_automation_without_an_id_links_to_the_list(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test an automation from YAML without an ID has no editor to link to."""
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "Haunted",
                    "triggers": [ARRIVED],
                    "conditions": [_checking("ghost")],
                    "actions": [],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_placeholders["edit"] == "/config/automation/dashboard"


BLUEPRINT = """
blueprint:
  name: Arrival
  domain: automation
  input:
    arrival_id:
      selector:
        text:
    checked_id:
      selector:
        text:
triggers:
  - trigger: event
    event_type: arrived
    id: !input arrival_id
conditions:
  - condition: trigger
    id: !input checked_id
actions: []
"""


@pytest.mark.parametrize(
    ("checked_id", "expected"),
    [("home", None), ("hmoe", {"hmoe"})],
)
async def test_an_automation_on_a_blueprint_is_read_with_its_inputs(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    tmp_path: Path,
    checked_id: str,
    expected: set[str] | None,
) -> None:
    """Test a blueprint's IDs are the ones its inputs fill in."""
    hass.config.config_dir = str(tmp_path)
    blueprint = tmp_path / "blueprints" / "automation" / "frenck" / "arrival.yaml"
    blueprint.parent.mkdir(parents=True)
    blueprint.write_text(BLUEPRINT, encoding="utf-8")

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "haunted",
                    "alias": "Haunted",
                    "use_blueprint": {
                        "path": "frenck/arrival.yaml",
                        "input": {"arrival_id": "home", "checked_id": checked_id},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("automation.haunted").state == "on"

    await SpookRepair(hass).async_inspect()

    issue = async_issue_about(issue_registry, ISSUE)
    found = None if issue is None else issue.translation_placeholders["trigger_ids"]
    assert found == (None if expected is None else "- `hmoe`")


async def test_a_draft_is_checked_for_unknown_trigger_ids(
    hass: HomeAssistant,
) -> None:
    """Test a draft automation is asked about its trigger IDs like a saved one."""
    assert await draft_checking.async_check_draft(
        hass,
        "automation",
        {
            "triggers": [ARRIVED],
            "conditions": [_checking("arived")],
            "actions": [],
        },
    ) == {"trigger_ids": ["arived"]}


@pytest.mark.parametrize(
    ("trigger", "checked_id"),
    [
        ({"trigger": "event", "event_type": "x", "id": 0}, "0"),
        ({"trigger": "event", "event_type": "x", "options": {"id": "x"}}, "x"),
    ],
)
async def test_a_draft_with_ids_that_cannot_be_known_is_left_alone(
    hass: HomeAssistant, trigger: dict[str, Any], checked_id: str
) -> None:
    """Test IDs Home Assistant refuses, or might lift from options, are skipped.

    A draft is not validated like a saved automation, so these get this far.
    """
    assert (
        await draft_checking.async_check_draft(
            hass,
            "automation",
            {
                "triggers": [trigger],
                "conditions": [_checking(checked_id)],
                "actions": [],
            },
        )
        == {}
    )


async def test_the_automation_id_is_not_a_trigger_id(hass: HomeAssistant) -> None:
    """Test a draft is not read as a condition itself, whatever its keys are."""
    assert (
        await draft_checking.async_check_draft(
            hass,
            "automation",
            {
                "id": "haunted",
                "condition": "trigger",
                "triggers": [ARRIVED],
                "actions": [],
            },
        )
        == {}
    )
