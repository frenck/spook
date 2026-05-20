"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.helpers import device_registry as dr

from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair
from ....util import async_filter_known_device_ids, async_get_all_device_ids

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced devices in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_device_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        dr.EVENT_DEVICE_REGISTRY_UPDATED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "devices"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _known_device_ids: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known device IDs for this inspection cycle."""
        self._known_device_ids = async_get_all_device_ids(self.hass)

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown device IDs referenced by ``entity``."""
        return async_filter_known_device_ids(
            self.hass,
            device_ids=entity.referenced_devices,
            known_device_ids=self._known_device_ids,
        )
