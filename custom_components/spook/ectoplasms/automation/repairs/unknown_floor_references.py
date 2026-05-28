"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import floor_registry as fr

from ....entity_filtering import async_filter_known_floor_ids, async_get_all_floor_ids
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced floors in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_floor_references"
    inspect_events = {
        fr.EVENT_FLOOR_REGISTRY_UPDATED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "floors"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _known_floor_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known floor IDs for this inspection cycle."""
        self._known_floor_ids = async_get_all_floor_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown floor IDs referenced by ``entity``."""
        return async_filter_known_floor_ids(
            self.hass,
            floor_ids=entity.referenced_floors,
            known_floor_ids=self._known_floor_ids,
        )
