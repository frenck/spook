"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)

from ....const import LOGGER
from ....entity_filtering import (
    async_filter_known_services,
    async_get_all_services,
    async_name_helper_in_the_registry,
    find_services_in_helper_options,
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
    }
    # Any integration, not just template: whether an action counts as missing
    # depends on whether the integration providing it is disabled, and that
    # can change without an action coming or going.
    inspect_config_entry_changed = True
    inspect_on_reload = "template"
    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Inspect template helper actions for unavailable services."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_services = async_get_all_services(self.hass)

        for entry in self.hass.config_entries.async_entries(self.domain):
            self.possible_issue_ids.add(entry.entry_id)

            services = find_services_in_helper_options(entry.options)

            unknown_services = async_filter_known_services(
                self.hass,
                services=services,
                known_services=known_services,
            )
            if not unknown_services:
                continue

            self.async_create_issue(
                issue_id=entry.entry_id,
                references=unknown_services,
                translation_placeholders={
                    "helper": entry.title,
                    "entity_id": async_name_helper_in_the_registry(
                        self.hass, entry.entry_id
                    ),
                    "edit": "/config/helpers",
                    "services": "\n".join(
                        f"- `{service}`" for service in sorted(unknown_services)
                    ),
                },
            )
