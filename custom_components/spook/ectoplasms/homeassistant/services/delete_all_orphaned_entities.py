"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.const import ATTR_RESTORED
from homeassistant.helpers import entity_registry as er

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to delete all orphaned entities."""

    domain = DOMAIN
    service = "delete_all_orphaned_entities"

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)
        for state in self.hass.states.async_all():
            if not state.attributes.get(ATTR_RESTORED):
                continue
            entity_registry.async_remove(state.entity_id)
            self.hass.states.async_remove(state.entity_id, call.context)
