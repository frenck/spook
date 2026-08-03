"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import (
    async_filter_known_services,
    async_find_services_in_sequence,
    async_get_all_services,
)
from ....repairs import AbstractSpookRepair


class SpookRepair(AbstractSpookRepair):
    """Spook repair finds unknown actions referenced in template helpers."""

    domain = "template"
    repair = "template_unknown_service_references"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "template"
    inspect_on_reload = "template"
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Inspect template helper actions for unavailable services."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_services = async_get_all_services(self.hass)

        for entry in self.hass.config_entries.async_entries(self.domain):
            self.possible_issue_ids.add(entry.entry_id)

            services = set()
            for option in entry.options.values():
                if not isinstance(option, list) or not all(
                    isinstance(step, dict) for step in option
                ):
                    continue
                services.update(async_find_services_in_sequence(option))

            unknown_services = async_filter_known_services(
                self.hass,
                services=services,
                known_services=known_services,
            )
            if not unknown_services:
                continue

            self.async_create_issue(
                issue_id=entry.entry_id,
                translation_placeholders={
                    "helper": entry.title,
                    "edit": "/config/helpers",
                    "services": "\n".join(
                        f"- `{service}`" for service in sorted(unknown_services)
                    ),
                },
            )
