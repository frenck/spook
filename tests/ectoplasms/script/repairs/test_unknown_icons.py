"""Tests for the repair about unknown icons in scripts."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component

from custom_components.spook import draft_checking
from custom_components.spook.ectoplasms.script.repairs.unknown_icons import (
    SpookRepair,
)
import pytest
from tests.icon_helpers import install_frontend, uninstall_frontend
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "script_unknown_icons_script.haunted"


async def _async_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, **config: Any
) -> str | None:
    """Set up a script, inspect it, and return the icons the issue reports."""
    assert await async_setup_component(hass, "group", {})
    assert await async_setup_component(
        hass, "script", {"script": {"haunted": {"sequence": [], **config}}}
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


async def test_the_icon_of_the_script_itself_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A script's own icon is drawn wherever the script is shown."""
    assert (
        await _async_reported(hass, issue_registry, icon="mdi:ghost-script")
        == "- `mdi:ghost-script`"
    )


async def test_an_icon_handed_to_an_action_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """An action with an icon field hands over an icon that is not drawn."""
    reported = await _async_reported(
        hass,
        issue_registry,
        icon="mdi:home",
        sequence=[
            {
                "action": "group.set",
                "data": {"object_id": "ghosts", "icon": "mdi:lightbulb-outlin"},
            }
        ],
    )

    assert reported == (
        "- `mdi:lightbulb-outlin` (did you mean `mdi:lightbulb-outline`?)"
    )


@pytest.mark.parametrize(
    "icon", ["mdi:home", "hass:ghost-script", "mdi:{{ 'ghost' }}", "mdi:esphome"]
)
async def test_what_is_not_judged(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, icon: str
) -> None:
    """Known icons, other sets and templates are left alone."""
    assert await _async_reported(hass, issue_registry, icon=icon) is None


async def test_no_frontend_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the frontend's list there is nothing to tell icons apart by."""
    uninstall_frontend(monkeypatch)

    assert await _async_reported(hass, issue_registry, icon="mdi:ghost") is None


async def test_a_draft_is_checked_for_unknown_icons(hass: HomeAssistant) -> None:
    """A draft script is asked about its icons like a saved one."""
    assert await async_setup_component(hass, "group", {})

    assert await draft_checking.async_check_draft(
        hass,
        "script",
        {
            "icon": "mdi:ghost-script",
            "sequence": [
                {
                    "action": "group.set",
                    "data": {"object_id": "ghosts", "icon": "mdi:home"},
                }
            ],
        },
    ) == {"icons": ["mdi:ghost-script"]}
