"""Spook - Your homie."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)
from homeassistant.helpers import config_validation as cv

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

            # Which options hold actions grows with every new template helper
            # type, so ask Home Assistant instead of keeping a list of keys.
            #
            # Validating is not just a shape check. The walker reads keys that
            # only exist after validation, so raw options make it raise on
            # shapes the action editor writes every day, a `parallel` block
            # among them. Validation normalizes those, and turns a templated
            # action name into a Template, which is not a string and so falls
            # out of the known-services filter on its own.
            services = set()
            for option in entry.options.values():
                try:
                    sequence = cv.SCRIPT_SCHEMA(option)
                except vol.Invalid:
                    continue

                services.update(async_find_services_in_sequence(sequence))

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
