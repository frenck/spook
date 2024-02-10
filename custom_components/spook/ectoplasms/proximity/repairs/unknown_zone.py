"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.helpers import entity_registry as er

from ....const import LOGGER
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

    _issues: set[str] = set()

    async def async_inspect(self) -> None:
        """Trigger a inspection."""
        LOGGER.debug("Spook is inspecting: %s", self.repair)

        coordinators: list[ProximityDataUpdateCoordinator] | None
        if not (coordinators := self.hass.data.get(self.domain)):
            return  # Nothing to do, proximity is not loaded

        entity_ids = {
            entity.entity_id for entity in self.entity_registry.entities.values()
        }.union(self.hass.states.async_entity_ids())

        possible_issue_ids: set[str] = set()
        for entry_id, coordinator in coordinators.items():
            if coordinator.proximity_zone_id not in entity_ids:
                possible_issue_ids.add(entry_id)
                self.async_create_issue(
                    issue_id=entry_id,
                    translation_placeholders={
                        "name": coordinator.name,
                        "zone": coordinator.proximity_zone_id,
                    },
                )
                self._issues.add(entry_id)
                LOGGER.debug(
                    "Spook found unknown zone %s in proximity %s "
                    "and created an issue for it",
                    coordinator.proximity_zone_id,
                    coordinator.name,
                )
            else:
                self.async_delete_issue(entry_id)
                self._issues.discard(entry_id)

        # Remove issues for entities that no longer exist
        for issue_id in self._issues - possible_issue_ids:
            self.async_delete_issue(issue_id)
            self._issues.discard(issue_id)
