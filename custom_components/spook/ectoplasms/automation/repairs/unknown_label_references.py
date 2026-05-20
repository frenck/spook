"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import label_registry as lr

from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair
from ....util import async_filter_known_label_ids, async_get_all_label_ids

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced labels in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_label_references"
    inspect_events = {
        lr.EVENT_LABEL_REGISTRY_UPDATED,
    }
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "labels"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _known_label_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known label IDs for this inspection cycle."""
        self._known_label_ids = async_get_all_label_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown label IDs referenced by ``entity``."""
        return async_filter_known_label_ids(
            self.hass,
            label_ids=entity.referenced_labels,
            known_label_ids=self._known_label_ids,
        )
