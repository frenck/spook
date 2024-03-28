"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
from ....repairs import AbstractSpookRepair
from ....util import async_filter_known_entity_ids, async_get_all_entity_ids

if TYPE_CHECKING:
    from homeassistant.components.proximity.coordinator import (
        ProximityDataUpdateCoordinator,
    )


class SpookRepair(AbstractSpookRepair):
    """Spook repair that tries to find unknown ignored zones used in proximity."""

    domain = "proximity"
    repair = "proximity_unknown_ignored_zones"
    inspect_events = {
        EVENT_COMPONENT_LOADED,
        er.EVENT_ENTITY_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = "proximity"

    automatically_clean_up_issues = True

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        coordinators: list[ProximityDataUpdateCoordinator] | None
        if not (coordinators := self.hass.data.get(self.domain)):
            return  # Nothing to do, proximity is not loaded

        known_entity_ids = async_get_all_entity_ids(self.hass)

        for entry_id, coordinator in coordinators.items():
            self.possible_issue_ids.add(entry_id)
            if unknown_entities := async_filter_known_entity_ids(
                self.hass,
                entity_ids=coordinator.ignored_zone_ids,
                known_entity_ids=known_entity_ids,
            ):
                self.async_create_issue(
                    issue_id=entry_id,
                    translation_placeholders={
                        "name": coordinator.name,
                        "zones": "\n".join(
                            f"- `{entity_id}`" for entity_id in unknown_entities
                        ),
                    },
                )
                LOGGER.debug(
                    "Spook found unknown zones in proximity %s "
                    "and created an issue for it; Zones %s",
                    coordinator.name,
                    ", ".join(unknown_entities),
                )
