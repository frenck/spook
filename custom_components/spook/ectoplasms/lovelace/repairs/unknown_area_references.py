"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar

from ....const import LOGGER
from ....dashboard_extraction import extract_areas_from_dashboard_node
from ....entity_filtering import async_filter_known_area_ids, async_get_all_area_ids
from ....repairs import AbstractSpookRepair
from ..dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced areas in dashboards."""

    domain = DOMAIN
    repair = "lovelace_unknown_area_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True
    automatically_clean_up_issues = True

    _dashboards: dict[str, LovelaceStorage | LovelaceYAML]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._dashboards = self.hass.data["lovelace"].dashboards
        await super().async_activate()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_area_ids = async_get_all_area_ids(self.hass)

        async for dashboard, url_path, config in async_dashboard_configs(
            self._dashboards
        ):
            self.possible_issue_ids.add(url_path)
            if config is None:
                continue

            extracted_areas = self.__async_extract_areas(config)
            if unknown_areas := async_filter_known_area_ids(
                self.hass,
                area_ids=set(extracted_areas),
                known_area_ids=known_area_ids,
            ):
                first_view_path = next(
                    path
                    for area_id, path in extracted_areas.items()
                    if area_id in unknown_areas
                )
                title = "Overview"
                if dashboard.config:
                    title = dashboard.config.get("title", url_path)
                self.async_create_issue(
                    issue_id=url_path,
                    translation_placeholders={
                        "areas": "\n".join(
                            f"- `{area_id}`" for area_id in sorted(unknown_areas)
                        ),
                        "dashboard": title,
                        "edit": f"/{url_path}/{first_view_path}?edit=1",
                    },
                )

    @callback
    def __async_extract_areas(self, config: dict[str, Any]) -> dict[str, int | str]:
        """Extract areas from a dashboard config, keyed by their view path."""
        areas: dict[str, int | str] = {}
        if isinstance(config, dict) and (views := config.get("views")):
            for view_index, view in enumerate(views):
                if not isinstance(view, dict):
                    continue
                view_path: int | str = view.get("path") or view_index
                for area_id in extract_areas_from_dashboard_node(view):
                    areas.setdefault(area_id, view_path)
        return areas
