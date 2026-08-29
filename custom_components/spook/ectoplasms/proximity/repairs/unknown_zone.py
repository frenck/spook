"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....entity_filtering import async_get_all_entity_ids
from ....repairs import AbstractSpookRepair

if TYPE_CHECKING:
    from homeassistant.components.proximity.coordinator import (
        ProximityDataUpdateCoordinator,
    )


class SpookRepair(AbstractSpookRepair):
    """Spook repair that tries to find unknown zones used in proximity."""

    domain = "proximity"
    repair = "proximity_unknown_zone"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "proximity"

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        known_entity_ids = async_get_all_entity_ids(self.hass)

        # Read off the config entries rather than `hass.data`. Proximity has
        # kept its coordinator on the entry since it became a config entry
        # integration, and only a loaded entry has one at all.
        for entry in self.hass.config_entries.async_loaded_entries(self.domain):
            coordinator: ProximityDataUpdateCoordinator = entry.runtime_data
            self.possible_issue_ids.add(entry.entry_id)
            if coordinator.proximity_zone_id not in known_entity_ids:
                self.async_create_issue(
                    issue_id=entry.entry_id,
                    translation_placeholders={
                        "name": coordinator.name,
                        "zone": coordinator.proximity_zone_id,
                    },
                )
                LOGGER.debug(
                    "Spook found unknown zone %s in proximity %s "
                    "and created an issue for it",
                    coordinator.proximity_zone_id,
                    coordinator.name,
                )
