"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components import automation
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_SERVICE_REGISTERED,
    EVENT_SERVICE_REMOVED,
)

from ....entity_filtering import (
    async_filter_known_services,
    async_find_services_in_sequence,
    async_get_all_services,
)
from ....repairs import AbstractSpookEntityComponentUnknownReferencesRepair

if TYPE_CHECKING:
    from typing import Any


class SpookRepair(AbstractSpookEntityComponentUnknownReferencesRepair):
    """Spook repair tries to find unknown referenced services in automations."""

    domain = automation.DOMAIN
    repair = "automation_unknown_service_references"
    inspect_events = {
        automation.EVENT_AUTOMATION_RELOADED,
        EVENT_COMPONENT_LOADED,
        EVENT_SERVICE_REGISTERED,
        EVENT_SERVICE_REMOVED,
    }
    inspect_config_entry_changed = True
    inspect_on_reload = True

    unavailable_entity_class = automation.UnavailableAutomationEntity
    entity_label = "automation"
    reference_label = "services"
    edit_url_pattern = "/config/automation/edit/{unique_id}"

    _known_services: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known services for this inspection cycle."""
        self._known_services = async_get_all_services(self.hass)

    def _should_inspect_entity(self, entity: Any) -> bool:
        """Skip disabled automations."""
        return entity.enabled

    async def _async_compute_unknown_references(self, entity: Any) -> set[str]:
        """Return unknown services called by ``entity``."""
        return async_filter_known_services(
            self.hass,
            services=async_find_services_in_sequence(entity.action_script.sequence),
            known_services=self._known_services,
        )
