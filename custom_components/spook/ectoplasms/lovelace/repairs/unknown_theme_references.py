"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.frontend import DATA_THEMES, DEFAULT_THEME, VALUE_NO_THEME
from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_LOVELACE_UPDATED,
    EVENT_THEMES_UPDATED,
)
from homeassistant.core import callback

from ....const import LOGGER
from ....dashboard_extraction import extract_themes_from_dashboard_view
from ....repairs import AbstractSpookRepair
from ..dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )

# The frontend's own look, built in and never in the list of themes, and the
# name Home Assistant itself uses for no theme at all.
_BUILT_IN_THEMES = frozenset({DEFAULT_THEME, VALUE_NO_THEME})

# What the frontend's theme picker used to write for "whatever the backend
# picked". Plenty of older dashboards still carry it, and the frontend still
# reads it as no theme, whatever its case.
_BACKEND_SELECTED = "backend-selected"


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find themes in dashboards that do not exist.

    The frontend only puts on a theme it has. A card or view naming one that
    was renamed or removed gets the default look, and nothing says why.
    """

    domain = DOMAIN
    repair = "lovelace_unknown_theme_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        EVENT_THEMES_UPDATED,
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

        # Without the frontend there is no list of themes to hold anything
        # against, and nothing that puts one on either. Home Assistant sets it
        # up before anything else, so this is a guard, not a waiting room.
        if (known_themes := self.hass.data.get(DATA_THEMES)) is None:
            return

        async for dashboard, url_path, config in async_dashboard_configs(
            self._dashboards
        ):
            self.possible_issue_ids.add(url_path)
            if config is None:
                continue

            themes = self.__async_extract_themes(config)
            unknown_themes = {
                theme
                for theme in themes
                if theme not in known_themes
                and theme not in _BUILT_IN_THEMES
                and theme.casefold() != _BACKEND_SELECTED
            }
            if not unknown_themes:
                continue

            first_view_path = next(
                view_path
                for theme, view_path in themes.items()
                if theme in unknown_themes
            )
            title = "Overview"
            if dashboard.config:
                title = dashboard.config.get("title", url_path)
            self.async_create_issue(
                issue_id=url_path,
                references=unknown_themes,
                translation_placeholders={
                    "themes": "\n".join(
                        f"- `{theme}`" for theme in sorted(unknown_themes)
                    ),
                    "dashboard": title,
                    "edit": f"/{url_path}/{first_view_path}?edit=1",
                },
            )

    @callback
    def __async_extract_themes(self, config: Any) -> dict[str, int | str]:
        """Extract the themes a dashboard puts on, keyed by their view path.

        A dashboard run by a strategy has no views stored, only the strategy,
        and the views it makes are not known until it opens.
        """
        themes: dict[str, int | str] = {}
        if (
            not isinstance(config, dict)
            or "strategy" in config
            or not isinstance(views := config.get("views"), list)
        ):
            return themes

        for view_index, view in enumerate(views):
            if not isinstance(view, dict):
                continue

            view_path: int | str = view.get("path") or view_index
            for theme in sorted(extract_themes_from_dashboard_view(view)):
                themes.setdefault(theme, view_path)

        return themes
