"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import area_registry as ar

from ....entity_filtering import async_filter_known_area_ids, async_get_all_area_ids
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced areas in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_area_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "areas"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _known_area_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known area IDs for this inspection cycle."""
        self._known_area_ids = async_get_all_area_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown area IDs referenced by ``entity``."""
        return async_filter_known_area_ids(
            self.hass,
            area_ids=entity.referenced_areas,
            known_area_ids=self._known_area_ids,
        )
