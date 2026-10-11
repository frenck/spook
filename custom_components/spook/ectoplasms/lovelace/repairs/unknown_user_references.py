"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.auth import EVENT_USER_ADDED, EVENT_USER_REMOVED
from homeassistant.components.lovelace import DOMAIN
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_LOVELACE_UPDATED
from homeassistant.core import callback

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....user_references import async_get_user_ids, extract_user_ids_from_view
from ..dashboards import async_dashboard_configs

if TYPE_CHECKING:
    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find users in dashboards that no longer exist.

    The frontend shows a card, badge, section or view only to the users its
    conditions list, and skips the confirmation of an action for the users
    exempted from it. It compares those IDs with whoever is looking, and says
    nothing about one that matches nobody. Removing a user leaves every such
    mention behind, and when it was the only one listed, the thing it guarded
    is hidden for everybody.
    """

    domain = DOMAIN
    repair = "lovelace_unknown_user_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        EVENT_USER_ADDED,
        EVENT_USER_REMOVED,
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

        known_user_ids = await async_get_user_ids(self.hass)

        async for dashboard, url_path, config in async_dashboard_configs(
            self._dashboards
        ):
            self.possible_issue_ids.add(url_path)
            if config is None:
                continue

            users = self.__async_extract_users(config)
            if not (unknown_users := set(users) - known_user_ids):
                continue

            first_view_path = next(
                path for user_id, path in users.items() if user_id in unknown_users
            )
            title = "Overview"
            if dashboard.config:
                title = dashboard.config.get("title", url_path)
            self.async_create_issue(
                issue_id=url_path,
                references=unknown_users,
                translation_placeholders={
                    "users": "\n".join(
                        f"- `{user_id}`" for user_id in sorted(unknown_users)
                    ),
                    "dashboard": title,
                    "edit": f"/{url_path}/{first_view_path}?edit=1",
                },
            )

    @callback
    def __async_extract_users(self, config: Any) -> dict[str, int | str]:
        """Extract the users a dashboard names, keyed by their view path.

        A dashboard run by a strategy makes its views when it opens, and has
        no users of its own to name.
        """
        users: dict[str, int | str] = {}
        if not isinstance(config, dict) or not isinstance(
            views := config.get("views"), list
        ):
            return users

        for view_index, view in enumerate(views):
            if not isinstance(view, dict):
                continue
            view_path: int | str = view.get("path") or view_index
            for user_id in sorted(extract_user_ids_from_view(view)):
                users.setdefault(user_id, view_path)

        return users
