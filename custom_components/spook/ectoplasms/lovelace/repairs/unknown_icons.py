"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.frontend import EVENT_PANELS_UPDATED
from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED
from homeassistant.core import callback

from ....const import LOGGER
from ....dashboard_extraction import extract_icons_from_dashboard_node
from ....icon_checking import async_get_mdi_icons, async_suggest
from ....repairs import AbstractSpookRepair
from ..dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )

# Where the icon a dashboard has in the sidebar is set.
_DASHBOARD_SETTINGS = "/config/lovelace/dashboards"


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds icons on dashboards that the frontend does not have.

    An `mdi:` icon that is not in the Material Design Icons set is drawn as
    an empty spot, without a word, wherever it is used: a card, a row, a
    badge, a view or the dashboard in the sidebar.
    """

    domain = DOMAIN
    repair = "lovelace_unknown_icons"
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

        icons = await async_get_mdi_icons(self.hass)

        async for dashboard, url_path, config in async_dashboard_configs(
            self._dashboards
        ):
            self.possible_issue_ids.add(url_path)
            if icons is None:
                continue

            # The icon in the sidebar is set with the dashboard, not in it.
            sidebar_icon = (dashboard.config or {}).get("icon")
            if icons.unknown_name(sidebar_icon) is None:
                sidebar_icon = None

            in_views = {
                icon: view_path
                for icon, view_path in self.__async_extract_icons(config).items()
                if icons.unknown_name(icon) is not None
            }

            found = list(in_views)
            if sidebar_icon is not None:
                found.append(sidebar_icon)

            if not found:
                continue

            await async_suggest(self.hass, icons, found)

            lines = [f"- {icons.describe(icon)}" for icon in sorted(in_views)]
            references = [f"{icon} in a view" for icon in in_views]
            if sidebar_icon is not None:
                lines.append(f"- {icons.describe(sidebar_icon)} in the sidebar")
                references.append(f"{sidebar_icon} in the sidebar")

            # Straight to the first view that has one, in edit mode.
            edit = _DASHBOARD_SETTINGS
            if in_views:
                edit = f"/{url_path}/{next(iter(in_views.values()))}?edit=1"

            title = "Overview"
            if dashboard.config:
                title = dashboard.config.get("title", url_path)
            self.async_create_issue(
                issue_id=url_path,
                references=references,
                translation_placeholders={
                    "icons": "\n".join(lines),
                    "dashboard": title,
                    "edit": edit,
                    "version": icons.version,
                },
            )

    @callback
    def __async_extract_icons(self, config: Any) -> dict[str, int | str]:
        """Extract the icons of a dashboard config, keyed by their view path."""
        icons: dict[str, int | str] = {}
        if not isinstance(config, dict) or not isinstance(
            views := config.get("views"), list
        ):
            return icons

        for view_index, view in enumerate(views):
            if not isinstance(view, dict):
                continue
            view_path: int | str = view.get("path") or view_index
            found = extract_icons_from_dashboard_node(view)

            # The frontend draws the tab of a view, whatever lays it out. A
            # custom layout only owns what is inside it.
            if isinstance(view_icon := view.get("icon"), str):
                found.add(view_icon)

            for icon in sorted(found):
                icons.setdefault(icon, view_path)
        return icons
