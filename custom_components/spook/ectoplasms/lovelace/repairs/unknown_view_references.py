"""Spook - Your homie."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from homeassistant.components.frontend import DATA_PANELS, EVENT_PANELS_UPDATED
from homeassistant.components.lovelace import DOMAIN
from homeassistant.components.lovelace.const import MODE_STORAGE
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED
from homeassistant.core import callback

from ....const import LOGGER
from ....dashboard_extraction import extract_navigation_paths_from_dashboard_node
from ....repairs import AbstractSpookRepair
from ..dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )

# What `||` in JavaScript passes over, like in the dashboard walk. A subview
# shows its back button on any `subview` the frontend finds true.
_JAVASCRIPT_FALSY = (None, "", 0, False)

# The frontend gives this name a page of its own, the list of unused entities,
# before it looks for a view by that name.
_UNUSED_ENTITIES_VIEW = "hass-unused-entities"

# Whatever a template or a card's own variables turn into is not known until
# they run. Jinja, button-card's `[[[ ]]]`, decluttering-card's `[[ ]]` and
# config-template-card's `${ }`.
_TEMPLATE_MARKERS = ("{{", "{%", "[[", "${")

# The browser drops these from a URL, or reads them as a slash, before the
# frontend gets to see the path. What it ends up as is the browser's call.
_REWRITTEN_BY_THE_BROWSER = ("\t", "\n", "\r", "\\")

# What `Number()` in JavaScript reads as a number. A view is looked up by that
# too, so `/dashboard/1` opens the second view, and so does `/dashboard/1.0`.
_JAVASCRIPT_WHITESPACE = re.compile(r"^[\s\ufeff]+|[\s\ufeff]+$")
_JAVASCRIPT_DECIMAL = re.compile(
    r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
)
_JAVASCRIPT_PREFIXED = re.compile(r"0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+")


def _javascript_number(text: str) -> float | None:
    """Return what `Number()` in JavaScript makes of a string, None for NaN."""
    text = _JAVASCRIPT_WHITESPACE.sub("", text)
    if not text:
        return 0.0

    if _JAVASCRIPT_PREFIXED.fullmatch(text):
        return float(int(text, 0))

    if _JAVASCRIPT_DECIMAL.fullmatch(text):
        return float(text)

    return None


def _dashboard_and_view(path: str) -> tuple[str, str] | None:
    """Return the dashboard and view a path opens, or None if unsure.

    Only a path from the root counts. A relative one lands wherever the
    browser happens to be, and `#name` alone opens a pop-up on the current
    view, like Bubble Card's.
    """
    if (
        not path.startswith("/")
        or path != path.strip()
        or any(marker in path for marker in _TEMPLATE_MARKERS)
        or any(character in path for character in _REWRITTEN_BY_THE_BROWSER)
    ):
        return None

    # The query string and the hash are not part of the route. Bubble Card
    # opens its pop-ups from a hash on a view, so the view still has to exist.
    segments = path.split("#", 1)[0].split("?", 1)[0].split("/")

    # The browser resolves these against the segments around them.
    if any(unquote(segment) in {".", ".."} for segment in segments):
        return None

    # Everything after the view is left to the view, the frontend only
    # reads the one segment.
    _, dashboard, *rest = segments
    return dashboard, rest[0] if rest else ""


def _view_paths_and_count(config: Any) -> tuple[set[str], int] | None:
    """Return the view paths and number of views, or None if not all known.

    A strategy makes its views when the dashboard opens, so a strategy
    dashboard has none stored, and a strategy view can give itself any path.
    """
    if not isinstance(config, dict) or "strategy" in config:
        return None

    views = config.get("views")
    if not isinstance(views, list) or not all(
        isinstance(view, dict) and "strategy" not in view for view in views
    ):
        return None

    # The frontend compares with `===`, so only a string is a path.
    paths = {path for view in views if isinstance(path := view.get("path"), str)}
    return paths, len(views)


def _opens_a_view(view: str, paths: set[str], count: int) -> bool:
    """Return whether the frontend finds a view for this path segment.

    The frontend decodes the segment with `decodeURI` and takes the first view
    whose path is it, or whose index is it read as a number. Both the segment
    as written and fully decoded are tried, since `decodeURI` leaves a few
    escapes like `%2F` alone and the other one does not.
    """
    if not view or view == _UNUSED_ENTITIES_VIEW:
        return True

    for candidate in (view, unquote(view)):
        if candidate in paths:
            return True

        number = _javascript_number(candidate)
        if number is not None and number.is_integer() and 0 <= number < count:
            return True

    return False


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find navigation to views that do not exist.

    The frontend opens the first view when it cannot find the one asked for,
    with the address still saying the other one. Nothing says the view is
    gone, so a renamed or deleted view leaves its buttons quietly pointing at
    the wrong place.
    """

    domain = DOMAIN
    repair = "lovelace_unknown_view_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        EVENT_PANELS_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True
    automatically_clean_up_issues = True

    _dashboards: dict[str | None, LovelaceStorage | LovelaceYAML]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._dashboards = self.hass.data["lovelace"].dashboards
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        # Read all of them first: every dashboard can navigate to every other.
        dashboards = [
            (dashboard, url_path, config)
            async for dashboard, url_path, config in async_dashboard_configs(
                self._dashboards
            )
        ]

        views_by_dashboard = self.__async_views_by_dashboard(dashboards)

        for dashboard, url_path, config in dashboards:
            self.possible_issue_ids.add(url_path)
            if config is None:
                continue

            navigation = self.__async_extract_navigation(config)
            unknown_paths = {
                path
                for path in navigation
                if self.__async_leads_nowhere(path, views_by_dashboard)
            }
            if not unknown_paths:
                continue

            first_view_path = next(
                view_path
                for path, view_path in navigation.items()
                if path in unknown_paths
            )
            title = "Overview"
            if dashboard.config:
                title = dashboard.config.get("title", url_path)
            self.async_create_issue(
                issue_id=url_path,
                references=unknown_paths,
                translation_placeholders={
                    "paths": "\n".join(f"- `{path}`" for path in sorted(unknown_paths)),
                    "dashboard": title,
                    "edit": f"/{url_path}/{first_view_path}?edit=1",
                },
            )

    @callback
    def __async_views_by_dashboard(
        self,
        dashboards: list[tuple[LovelaceStorage | LovelaceYAML, str, Any]],
    ) -> dict[str, tuple[set[str], int]]:
        """Return the views of each dashboard Spook can see all of.

        Only a dashboard stored by Home Assistant, read in full, that its own
        address really opens. A YAML dashboard can include views from files,
        and a dashboard whose panel could not be registered leaves its
        address to whatever got there first.
        """
        panels = self.hass.data.get(DATA_PANELS, {})

        views_by_dashboard: dict[str, tuple[set[str], int]] = {}
        for dashboard, url_path, config in dashboards:
            if (
                dashboard.mode != MODE_STORAGE
                or (panel := panels.get(url_path)) is None
                or panel.component_name != DOMAIN
            ):
                continue

            if (views := _view_paths_and_count(config)) is not None:
                views_by_dashboard[url_path] = views

        return views_by_dashboard

    @callback
    def __async_leads_nowhere(
        self,
        path: str,
        views_by_dashboard: dict[str, tuple[set[str], int]],
    ) -> bool:
        """Return whether a path is to a view a known dashboard does not have."""
        if (dashboard_and_view := _dashboard_and_view(path)) is None:
            return False

        dashboard, view = dashboard_and_view
        if (views := views_by_dashboard.get(dashboard)) is None:
            return False

        return not _opens_a_view(view, *views)

    @callback
    def __async_extract_navigation(self, config: Any) -> dict[str, int | str]:
        """Extract where a dashboard navigates to, keyed by their view path."""
        navigation: dict[str, int | str] = {}
        if not isinstance(config, dict) or not isinstance(
            views := config.get("views"), list
        ):
            return navigation

        for view_index, view in enumerate(views):
            if not isinstance(view, dict):
                continue

            view_path: int | str = view.get("path") or view_index

            # A subview's back button goes to its `back_path`. Only a subview
            # has one: on any other view it is never used.
            if view.get("subview") not in _JAVASCRIPT_FALSY and isinstance(
                back_path := view.get("back_path"), str
            ):
                navigation.setdefault(back_path, view_path)

            for path in sorted(extract_navigation_paths_from_dashboard_node(view)):
                navigation.setdefault(path, view_path)

        return navigation
