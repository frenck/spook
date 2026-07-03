"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.lovelace import DOMAIN
from homeassistant.components.lovelace.const import ConfigNotFound
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_LOVELACE_UPDATED,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import Event, callback
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....dashboard_extraction import extract_entities_from_dashboard_node
from ....entity_filtering import async_filter_known_entity_ids, async_get_all_entity_ids
from ....entity_suggestions import async_describe_unknown_entities
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.components.lovelace.dashboard import (
        LovelaceStorage,
        LovelaceYAML,
    )


class SpookRepair(AbstractSpookRepair):
    """Spook repair tries to find unknown referenced entity in dashboards."""

    domain = DOMAIN
    repair = "lovelace_unknown_entity_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_LOVELACE_UPDATED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True
    automatically_clean_up_issues = True

    _dashboards: dict[str, LovelaceStorage | LovelaceYAML]

    async def async_activate(self) -> None:
        """Handle the activating a repair."""
        self._dashboards = self.hass.data["lovelace"].dashboards
        await super().async_activate()

        @callback
        def _state_entity_changed(event_data: Mapping[str, Any]) -> bool:
            """Return if a state entity was added or removed."""
            return (
                event_data.get("old_state") is None
                or event_data.get("new_state") is None
            )

        @callback
        def _async_call_inspect_debouncer(_: Event) -> None:
            """Trigger an inspection when a state entity is added or removed."""
            self.inspect_debouncer.async_schedule_call()

        self._event_subs.add(
            self.hass.bus.async_listen(
                EVENT_STATE_CHANGED,
                _async_call_inspect_debouncer,
                event_filter=_state_entity_changed,
            ),
        )

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass, include_all_none=True)

        # Loop over all dashboards and check if there are unknown entities
        # referenced in the dashboards.
        for dashboard in self._dashboards.values():
            url_path = dashboard.url_path or "lovelace"
            self.possible_issue_ids.add(url_path)
            try:
                config = await dashboard.async_load(force=False)
            except ConfigNotFound:
                LOGGER.debug("Config for dashboard %s not found, skipping", url_path)
                continue

            extracted_entities = self.__async_extract_entities(config)
            if unknown_entities := async_filter_known_entity_ids(
                self.hass,
                entity_ids=set(extracted_entities.keys()),
                known_entity_ids=known_entity_ids,
            ):
                # Get the view path of the first unknown entity (by view order)
                first_view_path = next(
                    path
                    for entity_id, path in extracted_entities.items()
                    if entity_id in unknown_entities
                )
                title = "Overview"
                if dashboard.config:
                    title = dashboard.config.get("title", url_path)
                self.async_create_issue(
                    issue_id=url_path,
                    translation_placeholders={
                        "entities": async_describe_unknown_entities(
                            self.hass, sorted(unknown_entities)
                        ),
                        "dashboard": title,
                        "edit": f"/{url_path}/{first_view_path}?edit=1",
                    },
                )
                LOGGER.debug(
                    (
                        "Spook found unknown entities in dashboard %s "
                        "and created an issue for it; Entities: %s"
                    ),
                    title,
                    ", ".join(unknown_entities),
                )

    @callback
    def __async_extract_entities(self, config: dict[str, Any]) -> dict[str, int | str]:
        """Extract entities from a dashboard config, keyed by their view path."""
        entities: dict[str, int | str] = {}
        if isinstance(config, dict) and (views := config.get("views")):
            for view_index, view in enumerate(views):
                if not isinstance(view, dict):
                    continue
                view_path: int | str = view.get("path") or view_index
                for entity_id in extract_entities_from_dashboard_node(view):
                    entities.setdefault(entity_id, view_path)
        return entities
