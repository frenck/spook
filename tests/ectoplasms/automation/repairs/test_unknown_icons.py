"""Tests for the repair about unknown icons in automations."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.service import async_set_service_schema
from homeassistant.setup import async_setup_component

from custom_components.spook import draft_checking
from custom_components.spook.ectoplasms.automation.repairs.unknown_icons import (
    SpookRepair,
)
import pytest
from tests.icon_helpers import install_frontend, uninstall_frontend
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "automation_unknown_icons_automation.haunted"


def _set_group(icon: str, **step: Any) -> dict[str, Any]:
    """Return a step that gives a group this icon."""
    return {
        "action": "group.set",
        "data": {"object_id": "ghosts", "icon": icon},
        **step,
    }


async def _async_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, *actions: Any
) -> str | None:
    """Set up an automation with these actions, inspect, and return the icons."""
    assert await async_setup_component(hass, "group", {})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "id": "haunted",
                "alias": "Haunted",
                "triggers": [{"trigger": "event", "event_type": "boo"}],
                "actions": list(actions),
            }
        },
    )
    await hass.async_block_till_done()

    await SpookRepair(hass).async_inspect()

    if (issue := async_issue_about(issue_registry, _ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["icons"]


@pytest.fixture(autouse=True)
def _frontend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Install a frontend with a few icons."""
    install_frontend(monkeypatch, tmp_path)


async def test_an_unknown_icon_handed_to_an_action_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """An action with an icon field hands over an icon that is not drawn."""
    assert (
        await _async_reported(
            hass,
            issue_registry,
            _set_group("mdi:ghost-group"),
            _set_group("mdi:sofa"),
        )
        == "- `mdi:ghost-group`"
    )


async def test_an_icon_in_a_nested_block_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Steps inside other steps are walked into, whatever kind of block."""
    reported = await _async_reported(
        hass,
        issue_registry,
        {
            "choose": [
                {
                    "conditions": [],
                    "sequence": [{"if": [], "then": [_set_group("mdi:ghost-then")]}],
                }
            ],
            "default": [{"parallel": [_set_group("mdi:ghost-parallel")]}],
        },
    )

    assert reported == "- `mdi:ghost-parallel`\n- `mdi:ghost-then`"


async def test_a_near_miss_suggests_the_icon_it_meant(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A typo one letter off gets a suggestion."""
    assert await _async_reported(
        hass, issue_registry, _set_group("mdi:thermometr")
    ) == ("- `mdi:thermometr` (did you mean `mdi:thermometer`?)")


@pytest.mark.parametrize(
    "step",
    [
        _set_group("mdi:ghost-group", enabled=False),
        {"enabled": False, "sequence": [_set_group("mdi:ghost-group")]},
        _set_group("mdi:{{ 'ghost' }}"),
        _set_group("hass:ghost-group"),
        _set_group("phu:ghost-group"),
        # Only a field that says it takes an icon. `notify.html5` takes the
        # address of a picture under `icon`, and so do others.
        {"action": "notify.ghost", "data": {"icon": "mdi:ghost-group"}},
        # Values shaped like a step are only handed over, never run.
        {"variables": {"later": _set_group("mdi:ghost-group")}},
        {"event": "boo", "event_data": {"next": _set_group("mdi:ghost-group")}},
        {
            "repeat": {
                "for_each": [_set_group("mdi:ghost-group")],
                "sequence": [],
            }
        },
    ],
)
async def test_what_is_not_judged(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, step: dict[str, Any]
) -> None:
    """Turned off, templated, other sets, and fields that are not icons."""
    hass.services.async_register("notify", "ghost", lambda _: None)
    async_set_service_schema(
        hass,
        "notify",
        "ghost",
        {"fields": {"icon": {"selector": {"text": {}}}}},
    )

    assert await _async_reported(hass, issue_registry, step) is None


async def test_an_icon_field_in_a_section_is_read(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Fields grouped into a section of the action's description count too."""
    hass.services.async_register("ghost", "paint", lambda _: None)
    async_set_service_schema(
        hass,
        "ghost",
        "paint",
        {
            "fields": {
                "look": {
                    "collapsed": True,
                    "fields": {"badge": {"selector": {"icon": {}}}},
                }
            }
        },
    )

    assert (
        await _async_reported(
            hass,
            issue_registry,
            {"action": "ghost.paint", "data": {"badge": "mdi:ghost-badge"}},
        )
        == "- `mdi:ghost-badge`"
    )


async def test_no_frontend_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the frontend's list there is nothing to tell icons apart by."""
    uninstall_frontend(monkeypatch)

    assert (
        await _async_reported(hass, issue_registry, _set_group("mdi:ghost-group"))
        is None
    )


async def test_a_draft_is_checked_for_unknown_icons(hass: HomeAssistant) -> None:
    """A draft automation is asked about its icons like a saved one."""
    assert await async_setup_component(hass, "group", {})

    assert await draft_checking.async_check_draft(
        hass,
        "automation",
        {
            "triggers": [{"trigger": "event", "event_type": "haunt"}],
            "actions": [_set_group("mdi:ghost-group"), _set_group("mdi:sofa")],
        },
    ) == {"icons": ["mdi:ghost-group"]}
