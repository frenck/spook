"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, config_validation as cv
from homeassistant.core import ServiceResponse, SupportsResponse

from ....services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookService):
    """Home Assistant service to add an alias to an entity."""

    domain = DOMAIN
    service = "get_alias_from_entity"
    supports_response = SupportsResponse.ONLY
    schema = {
        vol.Required("entity"): cv.string,
    }

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)
        if not (entity := entity_registry.async_get(call.data["entity"])):
            msg = f"Entity {call.data['entity']} not found"
            raise HomeAssistantError(msg)

        if call.return_response:
            return {
                "aliases": entity.aliases
            }
        return None
