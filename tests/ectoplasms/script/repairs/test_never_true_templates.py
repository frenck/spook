"""Tests for the script templates that can never pass repair."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.setup import async_setup_component

from custom_components.spook import draft_checking
from custom_components.spook.ectoplasms.script.repairs.never_true_templates import (
    SpookRepair,
)
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

ISSUE = "script_never_true_templates_script.haunted"

FINE = "{{ is_state('light.hall', 'on') }}"
QUOTED = "\"{{ is_state('light.hall', 'on') }}\""
ON_OR_OFF = "{{ 'on' if is_state('light.hall', 'on') else 'off' }}"


def _template_condition(template: Any) -> dict[str, Any]:
    """Return a template condition."""
    return {"condition": "template", "value_template": template}


async def _found(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, sequence: list[Any]
) -> set[str] | None:
    """Set up the haunted script, inspect it, and return what is reported."""
    assert await async_setup_component(
        hass,
        "script",
        {"script": {"haunted": {"alias": "Haunted", "sequence": sequence}}},
    )
    await hass.async_block_till_done()
    assert hass.states.get("script.haunted")

    await SpookRepair(hass).async_inspect()

    if (issue := async_issue_about(issue_registry, ISSUE)) is None:
        return None
    return {
        line.removeprefix("- `").removesuffix("`")
        for line in issue.translation_placeholders["templates"].splitlines()
    }


async def test_a_quoted_condition_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a condition step with quotes around its template is reported."""
    assert await _found(hass, issue_registry, [_template_condition(QUOTED)]) == {QUOTED}

    issue = async_issue_about(issue_registry, ISSUE)
    assert issue
    assert issue.translation_key == "script_never_true_templates"
    assert issue.translation_placeholders == {
        "script": "Haunted",
        "edit": "/config/script/edit/haunted",
        "entity_id": "script.haunted",
        "templates": f"- `{QUOTED}`",
    }
    assert issue.learn_more_url == (
        "https://spook.boo/script#templates-that-can-never-pass"
    )


async def test_templates_in_a_sequence_are_found_wherever_they_nest(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test every place in a sequence a template has to pass is read."""
    assert await _found(
        hass,
        issue_registry,
        [
            {"wait_template": "on", "timeout": 1},
            {"condition": "{{ 'on' }}"},
            {
                "repeat": {
                    "until": [_template_condition(ON_OR_OFF)],
                    "sequence": [],
                }
            },
            {"if": [f"{{{{ 'x' }}}}{QUOTED}"], "then": []},
            {"wait_for_trigger": [{"trigger": "template", "value_template": QUOTED}]},
        ],
    ) == {"on", "{{ 'on' }}", ON_OR_OFF, f"{{{{ 'x' }}}}{QUOTED}", QUOTED}


@pytest.mark.parametrize(
    "sequence",
    [
        [_template_condition(FINE)],
        [_template_condition("true")],
        [{"wait_template": ON_OR_OFF, "timeout": 1}],
        [{"wait_template": "{{ states('input_text.answer') }}", "timeout": 1}],
        [{"wait_for_trigger": [{"trigger": "template", "value_template": ON_OR_OFF}]}],
        [{**_template_condition(QUOTED), "enabled": False}],
    ],
)
async def test_templates_that_can_pass_are_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, sequence: list[Any]
) -> None:
    """Test templates that can pass, depend on a run or are disabled are left alone."""
    assert await _found(hass, issue_registry, sequence) is None


async def test_a_script_that_failed_to_load_is_left_alone(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test a broken script is not reported: Home Assistant says so itself."""
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "haunted": {
                    "alias": "Haunted",
                    "sequence": [
                        _template_condition(QUOTED),
                        {"wait_for_trigger": [{"trigger": "no_such_platform"}]},
                    ],
                }
            }
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("script.haunted").state == "unavailable"

    await SpookRepair(hass).async_inspect()

    assert async_issue_about(issue_registry, ISSUE) is None


async def test_a_draft_is_checked_for_templates_that_never_pass(
    hass: HomeAssistant,
) -> None:
    """Test a draft script is asked about its templates like a saved one."""
    hass.states.async_set("light.hall", "on")
    assert await draft_checking.async_check_draft(
        hass,
        "script",
        {"sequence": [{"wait_template": QUOTED}, _template_condition(FINE)]},
    ) == {"templates": [QUOTED]}
