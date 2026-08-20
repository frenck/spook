"""Tests for the template helper unknown action references repair."""

# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.template.repairs.unknown_service_references import (
    SpookRepair,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir


def _issue_id(entry: MockConfigEntry) -> str:
    """Return the repair issue ID for a config entry."""
    return f"template_unknown_service_references_{entry.entry_id}"


async def test_unknown_action_in_template_button_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test template button actions referencing deleted scripts are reported."""
    entry = MockConfigEntry(
        domain="template",
        title="Clean everything",
        options={
            "name": "Clean everything",
            "template_type": "button",
            "press": [{"action": "script.1766687627449"}],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["edit"] == "/config/helpers"
    assert issue.translation_placeholders["services"] == "- `script.1766687627449`"


async def test_unknown_action_in_another_template_helper_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test all template helper action options are inspected."""
    entry = MockConfigEntry(
        domain="template",
        title="Ghostly switch",
        options={
            "name": "Ghostly switch",
            "template_type": "switch",
            "turn_on": [{"action": "script.missing_turn_on"}],
            "turn_off": [{"action": "script.working_turn_off"}],
        },
    )
    entry.add_to_hass(hass)
    hass.services.async_register("script", "working_turn_off", lambda _call: None)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["services"] == "- `script.missing_turn_on`"


async def test_templated_action_in_template_helper_creates_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test templated actions in raw template helper options are ignored."""
    entry = MockConfigEntry(
        domain="template",
        title="Dynamic notification",
        options={
            "name": "Dynamic notification",
            "template_type": "button",
            "press": [{"action": "{{ 'notify.' ~ who }}"}],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_parallel_shorthand_is_inspected(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a parallel block written as shorthand is walked, not fatal.

    The action editor stores a parallel block as `parallel: [<action>, ...]`,
    and Home Assistant only wraps that into a `sequence` while validating.
    Walking it raw raised `KeyError: 'sequence'`, which took down the whole
    inspection and left every later config entry uninspected.
    """
    entry = MockConfigEntry(
        domain="template",
        title="Parallel button",
        options={
            "name": "Parallel button",
            "template_type": "button",
            "press": [{"parallel": [{"action": "script.ghost"}]}],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.translation_placeholders["services"] == "- `script.ghost`"


async def test_nested_action_shapes_are_inspected(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test choose, if/then and repeat blocks are all walked."""
    entry = MockConfigEntry(
        domain="template",
        title="Nested button",
        options={
            "name": "Nested button",
            "template_type": "button",
            "press": [
                {
                    "choose": [
                        {
                            "conditions": [],
                            "sequence": [{"action": "script.ghost_choose"}],
                        },
                    ],
                },
                {
                    "if": [
                        {"condition": "state", "entity_id": "light.x", "state": "on"},
                    ],
                    "then": [{"action": "script.ghost_if"}],
                },
                {
                    "repeat": {
                        "count": 2,
                        "sequence": [{"action": "script.ghost_repeat"}],
                    },
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue
    assert issue.translation_placeholders["services"] == (
        "- `script.ghost_choose`\n- `script.ghost_if`\n- `script.ghost_repeat`"
    )


async def test_unparsable_option_is_skipped(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test options Home Assistant itself would reject are stepped over.

    A step with nothing to identify it, and a bare `repeat` without its
    sequence, both used to raise rather than being skipped.
    """
    entry = MockConfigEntry(
        domain="template",
        title="Broken button",
        options={
            "name": "Broken button",
            "template_type": "button",
            "press": [{"alias": "a note and nothing else"}],
            "unrelated": [{"repeat": {"count": 2}}],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_one_bad_entry_does_not_hide_the_next(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a helper Home Assistant cannot validate does not stop the scan.

    This is what made the crash expensive: the exception escaped
    `async_inspect`, so every config entry after the offending one went
    uninspected and the repair silently reported nothing at all.
    """
    broken = MockConfigEntry(
        domain="template",
        title="Broken first",
        options={
            "name": "Broken first",
            "template_type": "button",
            "press": [{"if": [{"condition": "state"}]}],
        },
    )
    broken.add_to_hass(hass)

    fine = MockConfigEntry(
        domain="template",
        title="Reportable second",
        options={
            "name": "Reportable second",
            "template_type": "button",
            "press": [{"action": "script.ghost"}],
        },
    )
    fine.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(broken)) is None
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(fine))


async def test_disabled_step_is_not_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a step the user disabled is skipped, as the walker already does."""
    entry = MockConfigEntry(
        domain="template",
        title="Parked button",
        options={
            "name": "Parked button",
            "template_type": "button",
            "press": [{"action": "script.ghost", "enabled": False}],
        },
    )
    entry.add_to_hass(hass)

    await SpookRepair(hass).async_inspect()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None


async def test_issue_clears_once_the_action_exists(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue disappears when the action is registered again."""
    entry = MockConfigEntry(
        domain="template",
        title="Recovering button",
        options={
            "name": "Recovering button",
            "template_type": "button",
            "press": [{"action": "script.comes_back"}],
        },
    )
    entry.add_to_hass(hass)

    repair = SpookRepair(hass)
    await repair._async_inspect_with_cleanup()
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry))

    hass.services.async_register("script", "comes_back", lambda _call: None)
    await repair._async_inspect_with_cleanup()

    assert issue_registry.async_get_issue(DOMAIN, _issue_id(entry)) is None
