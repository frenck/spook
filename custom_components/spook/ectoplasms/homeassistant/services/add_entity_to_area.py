"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    entity_registry as er,
)

from ....errors import area_not_found
from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add a entity to an area."""

    domain = DOMAIN
    service = "add_entity_to_area"
    schema = {
        vol.Required("area_id"): cv.string,
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        area_registry = ar.async_get(self.hass)
        if not area_registry.async_get_area(call.data["area_id"]):
            raise area_not_found(call.data["area_id"])

        entity_registry = er.async_get(self.hass)
        for entity_id in call.data["entity_id"]:
            entity_registry.async_update_entity(
                entity_id,
                area_id=call.data["area_id"],
            )
