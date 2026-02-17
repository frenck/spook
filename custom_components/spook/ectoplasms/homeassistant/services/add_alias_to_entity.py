"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add an alias to an entity."""

    domain = DOMAIN
    service = "add_alias_to_entity"
    schema = {
        vol.Required("entity"): cv.string,
        vol.Required("alias"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_registry = er.async_get(self.hass)
        if not (entity := entity_registry.async_get(call.data["entity"])):
            msg = f"Entity {call.data['entity']} not found"
            raise HomeAssistantError(msg)

        aliases = entity.aliases.copy()
        entity_registry.async_update_entity(
            entity_id=call.data["entity"],
            aliases=aliases.union(call.data["alias"]),
        )
