"""Tests for the repair about unknown icons on dashboards."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from custom_components.spook.ectoplasms.lovelace.repairs.unknown_icons import (
    SpookRepair,
)
import pytest
from tests.icon_helpers import ICON_VERSION, install_frontend, uninstall_frontend
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "lovelace_unknown_icons_lovelace"


def _dashboard(
    *cards: Any, sidebar_icon: str | None = None, **view: Any
) -> SimpleNamespace:
    """Return a dashboard with these cards on its second view."""
    config = {
        "views": [
            {"path": "home", "cards": [{"type": "tile", "icon": "mdi:home"}]},
            {"path": "kitchen", "cards": list(cards), **view},
        ]
    }

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the same config every time, like a dashboard nobody saved."""
        del force
        return config

    settings: dict[str, Any] = {"title": "Overview"}
    if sidebar_icon is not None:
        settings["icon"] = sidebar_icon
    return SimpleNamespace(url_path="lovelace", config=settings, async_load=async_load)


async def _async_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, dashboard: SimpleNamespace
) -> dict[str, str] | None:
    """Inspect a dashboard, and return what the issue says, if any."""
    repair = SpookRepair(hass)
    repair._dashboards = {"lovelace": dashboard}  # noqa: SLF001
    await repair.async_inspect()
    if (issue := async_issue_about(issue_registry, _ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders


@pytest.fixture(autouse=True)
def _frontend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Install a frontend with a few icons."""
    install_frontend(monkeypatch, tmp_path)


@pytest.mark.parametrize(
    "card",
    [
        {"type": "button", "entity": "light.kitchen", "icon": "mdi:ghost-bulb"},
        {
            "type": "entities",
            "entities": [{"entity": "light.a", "icon": "mdi:ghost-bulb"}],
        },
        {"type": "entities", "title": "Lights", "icon": "mdi:ghost-bulb"},
        {
            "type": "picture-elements",
            "image": "/local/plan.png",
            "elements": [{"type": "icon", "icon": "mdi:ghost-bulb"}],
        },
        {"type": "heading", "heading": "Kitchen", "icon": "mdi:ghost-bulb"},
        {
            "type": "heading",
            "heading": "Kitchen",
            "badges": [
                {"type": "entity", "entity": "light.a", "icon": "mdi:ghost-bulb"}
            ],
        },
        {
            "type": "vertical-stack",
            "cards": [{"type": "tile", "entity": "light.a", "icon": "mdi:ghost-bulb"}],
        },
        # A card of the frontend's own inside a third-party one is drawn by
        # the frontend all the same.
        {
            "type": "custom:stack-in-card",
            "cards": [{"type": "tile", "entity": "light.a", "icon": "mdi:ghost-bulb"}],
        },
    ],
)
async def test_an_unknown_icon_on_a_card_is_reported(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Whatever the frontend draws an icon on, it is looked at."""
    reported = await _async_reported(hass, issue_registry, _dashboard(card))

    assert reported == {
        "icons": "- `mdi:ghost-bulb`",
        "dashboard": "Overview",
        "edit": "/lovelace/kitchen?edit=1",
        "version": ICON_VERSION,
    }


async def test_view_and_badge_icons_are_looked_at(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A view's own icon, and those of its badges, are drawn too."""
    dashboard = _dashboard(
        badges=[{"type": "entity", "entity": "light.a", "icon": "mdi:ghost-badge"}],
        icon="mdi:ghost-view",
    )

    reported = await _async_reported(hass, issue_registry, dashboard)

    assert reported
    assert reported["icons"] == "- `mdi:ghost-badge`\n- `mdi:ghost-view`"


async def test_the_tab_icon_of_a_custom_layout_view_is_looked_at(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """The frontend draws the tab, whatever lays out the view itself."""
    dashboard = _dashboard(type="custom:grid-layout", icon="mdi:ghost-view")

    reported = await _async_reported(hass, issue_registry, dashboard)

    assert reported
    assert reported["icons"] == "- `mdi:ghost-view`"


async def test_the_sidebar_icon_points_at_the_dashboard_settings(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """The sidebar icon is set with the dashboard, not in it."""
    reported = await _async_reported(
        hass, issue_registry, _dashboard(sidebar_icon="mdi:ghost-sidebar")
    )

    assert reported
    assert reported["icons"] == "- `mdi:ghost-sidebar` in the sidebar"
    assert reported["edit"] == "/config/lovelace/dashboards"


async def test_a_near_miss_suggests_the_icon_it_meant(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A typo one letter off gets a suggestion."""
    reported = await _async_reported(
        hass,
        issue_registry,
        _dashboard({"type": "button", "icon": "mdi:lightbulb-outlin"}),
    )

    assert reported
    assert reported["icons"] == (
        "- `mdi:lightbulb-outlin` (did you mean `mdi:lightbulb-outline`?)"
    )


@pytest.mark.parametrize(
    "card",
    [
        {"type": "button", "icon": "mdi:lightbulb"},
        {"type": "button", "icon": "hass:ghost-bulb"},
        {"type": "button", "icon": "phu:ghost-bulb"},
        {"type": "button", "icon": "mdi:{{ states('input_text.icon') }}"},
        # A third-party card does what it likes with an icon.
        {"type": "custom:button-card", "icon": "mdi:ghost-bulb"},
        {
            "type": "custom:mushroom-chips-card",
            "chips": [{"icon": "mdi:ghost-bulb"}],
        },
        {"type": "custom:button-card", "icon": "mdi:[[[ return 'ghost' ]]]"},
        # What a button hands to an action is the action's own data.
        {
            "type": "button",
            "tap_action": {
                "action": "perform-action",
                "perform_action": "group.set",
                "data": {"object_id": "ghosts", "icon": "mdi:ghost-bulb"},
            },
        },
    ],
)
async def test_what_is_not_judged(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, card: dict[str, Any]
) -> None:
    """Known icons, other sets, templates and third-party cards are left."""
    assert await _async_reported(hass, issue_registry, _dashboard(card)) is None


async def test_no_frontend_means_nothing_is_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the frontend's list there is nothing to tell icons apart by."""
    uninstall_frontend(monkeypatch)

    assert (
        await _async_reported(
            hass,
            issue_registry,
            _dashboard(
                {"type": "button", "icon": "mdi:ghost-bulb"},
                sidebar_icon="mdi:ghost-sidebar",
            ),
        )
        is None
    )
