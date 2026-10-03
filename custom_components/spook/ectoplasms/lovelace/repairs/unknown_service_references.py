"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_LOVELACE_UPDATED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.core import callback

from ....const import LOGGER
from ....dashboard_extraction import extract_actions_from_dashboard_node
from ....entity_filtering import async_filter_known_services, async_get_all_services
from ....repairs import AbstractSpookRepair
from ..dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown actions performed by dashboards.

    A button whose action is gone does nothing when tapped, and says nothing
    either, until somebody taps it.
    """

    domain = DOMAIN
    repair = "lovelace_unknown_service_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
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

        known_services = async_get_all_services(self.hass)

        async for dashboard, url_path, config in async_dashboard_configs(
            self._dashboards
        ):
            self.possible_issue_ids.add(url_path)
            if config is None:
                continue

            extracted_actions = self.__async_extract_actions(config)
            if unknown_actions := async_filter_known_services(
                self.hass,
                services=set(extracted_actions),
                known_services=known_services,
            ):
                first_view_path = next(
                    path
                    for action, path in extracted_actions.items()
                    if action in unknown_actions
                )
                title = "Overview"
                if dashboard.config:
                    title = dashboard.config.get("title", url_path)
                self.async_create_issue(
                    issue_id=url_path,
                    references=unknown_actions,
                    translation_placeholders={
                        "services": "\n".join(
                            f"- `{action}`" for action in sorted(unknown_actions)
                        ),
                        "dashboard": title,
                        "edit": f"/{url_path}/{first_view_path}?edit=1",
                    },
                )

    @callback
    def __async_extract_actions(self, config: dict[str, Any]) -> dict[str, int | str]:
        """Extract actions from a dashboard config, keyed by their view path."""
        actions: dict[str, int | str] = {}
        if isinstance(config, dict) and (views := config.get("views")):
            for view_index, view in enumerate(views):
                if not isinstance(view, dict):
                    continue
                view_path: int | str = view.get("path") or view_index
                for action in extract_actions_from_dashboard_node(view):
                    actions.setdefault(action, view_path)
        return actions
