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
    async_find_services_in_sequence,
    async_get_all_services,
    async_get_disabled_integrations,
    filter_known_services,
)
from . import AbstractSpookAutomationReferencesRepair

if TYPE_CHECKING:
    from ....repairs import InspectedEntity


class SpookRepair(AbstractSpookAutomationReferencesRepair):
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
    _disabled_integrations: set[str]

    async def _async_setup_inspection(self) -> None:
        """Cache known services for this inspection cycle."""
        self._known_services = async_get_all_services(self.hass)
        self._disabled_integrations = async_get_disabled_integrations(self.hass)

    def _compute_unknown_references(self, entity: InspectedEntity) -> set[str]:
        """Return unknown services called by ``entity``."""
        return filter_known_services(
            async_find_services_in_sequence(entity.action_sequence),
            self._known_services,
            self._disabled_integrations,
        )
