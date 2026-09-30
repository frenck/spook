"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....services import AbstractSpookAdminService
from ..entity_registry_entries import async_get_registry_entries

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to set the icon of an entity.

    The same setting as in the entity's settings dialog. `null` takes it away
    again, and the entity goes back to the icon its integration gives it.
    """

    domain = DOMAIN
    service = "set_entity_icon"
    schema = {
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("icon"): vol.Any(None, cv.icon),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)

        for entry in async_get_registry_entries(self.hass, call.data["entity_id"]):
            entity_registry.async_update_entity(entry.entity_id, icon=call.data["icon"])
