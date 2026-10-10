"""Tests for the Lovelace unknown views repair."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.lovelace.const import ConfigNotFound

from custom_components.spook.ectoplasms.lovelace.repairs.unknown_view_references import (
    SpookRepair,
)
import pytest
from tests.repair_helpers import async_issue_about

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir

_ISSUE = "lovelace_unknown_view_references_lovelace"

# The views every target dashboard in these tests has, unless a test says
# otherwise: a path, a number, a path with a space, and one without a path.
_VIEWS = [
    {"path": "home", "cards": []},
    {"path": "bedroom", "cards": []},
    {"path": "living room", "cards": []},
    {"cards": []},
]


def _dashboard(
    url_path: str,
    config: dict[str, Any] | None,
    *,
    mode: str = "storage",
) -> SimpleNamespace:
    """Return a dashboard with this config, or one that has none stored."""

    async def async_load(*, force: bool) -> dict[str, Any]:
        """Return the dashboard config."""
        del force
        if config is None:
            raise ConfigNotFound
        return config

    return SimpleNamespace(
        url_path=url_path,
        config={"title": url_path.title()},
        mode=mode,
        async_load=async_load,
    )


def _navigating(path: Any, **card: Any) -> dict[str, Any]:
    """Return a button that navigates to this path when tapped."""
    return {
        "type": "button",
        "tap_action": {"action": "navigate", "navigation_path": path},
        **card,
    }


def _lovelace_with(*cards: dict[str, Any]) -> SimpleNamespace:
    """Return the default dashboard, with these cards on its second view."""
    return _dashboard(
        "lovelace",
        {"views": [_VIEWS[0], {"path": "bedroom", "cards": list(cards)}, *_VIEWS[2:]]},
    )


async def _async_inspect(
    hass: HomeAssistant,
    *dashboards: SimpleNamespace,
    panels: tuple[str, ...] | None = None,
) -> SpookRepair:
    """Inspect these dashboards, each served by a dashboard panel of its own."""
    for url_path in panels if panels is not None else [d.url_path for d in dashboards]:
        async_register_built_in_panel(hass, "lovelace", frontend_url_path=url_path)

    repair = SpookRepair(hass)
    repair._dashboards = {  # noqa: SLF001
        dashboard.url_path: dashboard for dashboard in dashboards
    }
    await repair._async_inspect_with_cleanup()  # noqa: SLF001
    return repair


def _reported_paths(issue_registry: ir.IssueRegistry) -> str | None:
    """Return the paths the issue on the default dashboard lists, if any."""
    if (issue := async_issue_about(issue_registry, _ISSUE)) is None:
        return None
    assert issue.translation_placeholders
    return issue.translation_placeholders["paths"]


async def test_navigating_to_a_missing_view_creates_an_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a button navigating to a view the dashboard lacks is reported."""
    await _async_inspect(
        hass,
        _lovelace_with(_navigating("/lovelace/home"), _navigating("/lovelace/attic")),
    )

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_placeholders == {
        "paths": "- `/lovelace/attic`",
        "dashboard": "Lovelace",
        "edit": "/lovelace/bedroom?edit=1",
    }


async def test_fixing_the_path_clears_the_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue goes away once the button points at a view that exists."""
    repair = await _async_inspect(hass, _lovelace_with(_navigating("/lovelace/attic")))
    assert async_issue_about(issue_registry, _ISSUE)

    repair._dashboards = {  # noqa: SLF001
        "lovelace": _lovelace_with(_navigating("/lovelace/home"))
    }
    await repair._async_inspect_with_cleanup()  # noqa: SLF001

    assert async_issue_about(issue_registry, _ISSUE) is None


@pytest.mark.parametrize(
    "card",
    [
        {
            "type": "button",
            "hold_action": {"action": "navigate", "navigation_path": "/lovelace/attic"},
        },
        {
            "type": "custom:mushroom-entity-card",
            "icon_tap_action": {
                "action": "navigate",
                "navigation_path": "/lovelace/attic",
            },
        },
        {
            "type": "vertical-stack",
            "cards": [_navigating("/lovelace/attic")],
        },
        {"type": "area", "area": "kitchen", "navigation_path": "/lovelace/attic"},
    ],
    ids=["hold-action", "custom-card-key", "nested", "area-card"],
)
async def test_navigation_anywhere_on_a_card_is_read(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    card: dict[str, Any],
) -> None:
    """Test navigation is found whatever key or card it sits under.

    The area card still has the `navigation_path` of its own from before it
    had a tap action.
    """
    await _async_inspect(hass, _lovelace_with(card))

    assert _reported_paths(issue_registry) == "- `/lovelace/attic`"


@pytest.mark.parametrize("action", ["perform-action", "call-service"])
@pytest.mark.parametrize("payload_key", ["data", "service_data", "target"])
async def test_navigation_in_what_an_action_is_handed_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    action: str,
    payload_key: str,
) -> None:
    """Test a navigate shape inside a performed action's payload is not read.

    Home Assistant gets it as data for the action, and nothing navigates.
    """
    card = {
        "type": "button",
        "tap_action": {
            "action": action,
            "perform_action": "browser_mod.navigate",
            payload_key: {"action": "navigate", "navigation_path": "/lovelace/attic"},
        },
    }

    await _async_inspect(hass, _lovelace_with(card))

    assert _reported_paths(issue_registry) is None


async def test_an_area_card_with_a_tap_action_ignores_its_old_path(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the area card's own path is not read when a tap action replaces it.

    The frontend only uses it when the card has no tap action.
    """
    card = {
        "type": "area",
        "area": "kitchen",
        "navigation_path": "/lovelace/attic",
        "tap_action": {"action": "more-info"},
    }
    await _async_inspect(hass, _lovelace_with(card))

    assert _reported_paths(issue_registry) is None


async def test_a_subview_back_path_to_a_missing_view_is_reported(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the back button of a subview is read, and only of a subview.

    Any other view never shows the back button, so its `back_path` is unused.
    """
    await _async_inspect(
        hass,
        _dashboard(
            "lovelace",
            {
                "views": [
                    *_VIEWS,
                    {"path": "lamp", "subview": True, "back_path": "/lovelace/attic"},
                    {"path": "fan", "subview": False, "back_path": "/lovelace/cellar"},
                ]
            },
        ),
    )

    issue = async_issue_about(issue_registry, _ISSUE)
    assert issue
    assert issue.translation_placeholders
    assert issue.translation_placeholders["paths"] == "- `/lovelace/attic`"
    assert issue.translation_placeholders["edit"] == "/lovelace/lamp?edit=1"


@pytest.mark.parametrize(
    "path",
    [
        "/lovelace/attic?edit=1",
        "/lovelace/attic#kitchen-popup",
        "/lovelace/attic/more",
        "/lovelace/4",
        "/lovelace/-1",
        "/lovelace/1.5",
        "/lovelace/Home",
    ],
    ids=["query", "hash", "deeper", "index-too-high", "negative", "fraction", "case"],
)
async def test_paths_the_frontend_finds_no_view_for(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    path: str,
) -> None:
    """Test the view is read the way the frontend reads it, and missing.

    Only the segment after the dashboard is the view, the query string and the
    hash are not part of it. A number past the last view is no view at all,
    and a path is compared exactly.
    """
    await _async_inspect(hass, _lovelace_with(_navigating(path)))

    assert _reported_paths(issue_registry) == f"- `{path}`"


@pytest.mark.parametrize(
    "path",
    [
        "/lovelace",
        "/lovelace/",
        "/lovelace?edit=1",
        "/lovelace/home",
        "/lovelace/home?edit=1",
        "/lovelace/home#kitchen-popup",
        "/lovelace/home/more",
        "/lovelace/3",
        "/lovelace/1.0",
        "/lovelace/0x1",
        "/lovelace/1e0",
        "/lovelace/+1",
        "/lovelace/%201",
        "/lovelace/living%20room",
        "/lovelace/living room",
        "/lovelace/hass-unused-entities",
    ],
)
async def test_paths_the_frontend_finds_a_view_for(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    path: str,
) -> None:
    """Test a path the frontend opens a view for is not reported.

    No view at all opens the first one. A view is found by its path, after
    decoding, or by its index read the way JavaScript's `Number()` reads it.
    The unused entities page is not a view, but it is there.
    """
    await _async_inspect(hass, _lovelace_with(_navigating(path)))

    assert _reported_paths(issue_registry) is None


@pytest.mark.parametrize(
    "path",
    [
        "attic",
        "../attic",
        "#attic",
        "/config/areas/dashboard",
        "/history",
        "/lovelace/{{ states('input_select.room') }}",
        "/lovelace/{# set by a card #}attic",
        "/lovelace/[[[ return variables.room ]]]",
        "/lovelace/[[room]]",
        "/lovelace/${vars[0]}",
        "/lovelace/home ",
        "/lovelace/ho\tme",
        "/lovelace/attic\\..\\home",
        "/lovelace/attic/../home",
        "/lovelace/attic/%2e%2e/home",
    ],
    ids=[
        "relative",
        "relative-up",
        "hash-only",
        "config-panel",
        "history-panel",
        "jinja",
        "jinja-comment",
        "button-card",
        "decluttering-card",
        "config-template-card",
        "trailing-space",
        "tab",
        "backslash",
        "dot-segment",
        "encoded-dot-segment",
    ],
)
async def test_paths_spook_cannot_be_sure_of_are_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    path: str,
) -> None:
    """Test a path is only judged when where it lands is certain.

    A relative path or a lone hash depends on where the browser is. Another
    panel is not a dashboard. A template is not known until it runs. And the
    browser rewrites a few things in a path before the frontend sees it,
    which in every one of these lands on a view that exists.
    """
    await _async_inspect(hass, _lovelace_with(_navigating(path)))

    assert _reported_paths(issue_registry) is None


async def test_a_path_that_is_not_text_is_left_alone(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a navigation path that is not a string does not trip the repair."""
    await _async_inspect(hass, _lovelace_with(_navigating(["/lovelace/attic"])))

    assert _reported_paths(issue_registry) is None


async def test_navigation_to_another_dashboard_is_checked(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a path into another dashboard is checked against that one."""
    await _async_inspect(
        hass,
        _lovelace_with(
            _navigating("/dashboard-rooms/kitchen"),
            _navigating("/dashboard-rooms/attic"),
        ),
        _dashboard("dashboard-rooms", {"views": [{"path": "kitchen"}]}),
    )

    assert _reported_paths(issue_registry) == "- `/dashboard-rooms/attic`"


async def test_a_view_path_that_is_not_text_matches_nothing(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a view path is only matched when it is a string.

    The frontend compares the path with `===`, so a view with the number 5 as
    its path is not what `/dashboard-rooms/5` opens.
    """
    await _async_inspect(
        hass,
        _lovelace_with(_navigating("/dashboard-rooms/5")),
        _dashboard("dashboard-rooms", {"views": [{"path": 5}, {"path": "kitchen"}]}),
    )

    assert _reported_paths(issue_registry) == "- `/dashboard-rooms/5`"


@pytest.mark.parametrize(
    ("target", "panels"),
    [
        (
            _dashboard(
                "dashboard-rooms", {"views": [{"path": "kitchen"}]}, mode="yaml"
            ),
            ("lovelace", "dashboard-rooms"),
        ),
        (
            _dashboard(
                "dashboard-rooms",
                {"strategy": {"type": "areas"}, "views": [{"path": "kitchen"}]},
            ),
            ("lovelace", "dashboard-rooms"),
        ),
        (
            _dashboard(
                "dashboard-rooms",
                {"views": [{"path": "kitchen"}, {"strategy": {"type": "area"}}]},
            ),
            ("lovelace", "dashboard-rooms"),
        ),
        (
            _dashboard("dashboard-rooms", None),
            ("lovelace", "dashboard-rooms"),
        ),
        (
            _dashboard("dashboard-rooms", {"title": "No views"}),
            ("lovelace", "dashboard-rooms"),
        ),
        (
            _dashboard("dashboard-rooms", {"views": [{"path": "kitchen"}, None]}),
            ("lovelace", "dashboard-rooms"),
        ),
        (
            _dashboard("dashboard-rooms", {"views": [{"path": "kitchen"}]}),
            ("lovelace",),
        ),
    ],
    ids=[
        "yaml",
        "strategy-dashboard",
        "strategy-view",
        "never-saved",
        "no-views",
        "broken-view",
        "no-panel",
    ],
)
async def test_dashboards_spook_cannot_see_all_views_of_are_not_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    target: SimpleNamespace,
    panels: tuple[str, ...],
) -> None:
    """Test only a dashboard whose every view Spook can read is judged.

    A YAML dashboard can include views from other files. A strategy makes its
    views, and their paths, when the dashboard opens, whatever views are
    stored next to it, and so does a dashboard that was never saved. And a dashboard whose panel could not be registered
    does not own its address.
    """
    await _async_inspect(
        hass,
        _lovelace_with(_navigating("/dashboard-rooms/attic")),
        target,
        panels=panels,
    )

    assert _reported_paths(issue_registry) is None


async def test_an_address_another_panel_owns_is_not_judged(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a dashboard is not judged when its address opens something else.

    The dashboard is kept even when its panel could not be registered, and
    whatever got the address first answers it.
    """
    async_register_built_in_panel(hass, "iframe", frontend_url_path="dashboard-rooms")

    await _async_inspect(
        hass,
        _lovelace_with(_navigating("/dashboard-rooms/attic")),
        _dashboard("dashboard-rooms", {"views": [{"path": "kitchen"}]}),
        panels=("lovelace",),
    )

    assert _reported_paths(issue_registry) is None


async def test_a_dashboard_without_views_is_fine_to_open(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test opening a dashboard that has no views yet is not reported.

    Without a view in the path nothing is looked up, so there is nothing
    missing. Read as a number, the empty view would be index 0, which a
    dashboard without views does not have.
    """
    await _async_inspect(
        hass,
        _lovelace_with(_navigating("/dashboard-empty")),
        _dashboard("dashboard-empty", {"views": []}),
    )

    assert _reported_paths(issue_registry) is None
