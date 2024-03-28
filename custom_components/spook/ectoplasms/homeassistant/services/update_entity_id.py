"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, entity_registry as er

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to update an entity's ID."""

    domain = DOMAIN
    service = "update_entity_id"
    schema = {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("new_entity_id"): cv.entity_id,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)
        entity_registry.async_update_entity(
            entity_id=call.data["entity_id"],
            new_entity_id=call.data["new_entity_id"],
        )
