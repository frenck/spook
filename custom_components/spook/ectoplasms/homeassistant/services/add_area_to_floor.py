"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    floor_registry as fr,
)

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add an area to a floor."""

    domain = DOMAIN
    service = "add_area_to_floor"
    schema = {
        vol.Required("floor_id"): cv.string,
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        floor_registry = fr.async_get(self.hass)
        if not floor_registry.async_get_floor(call.data["floor_id"]):
            msg = f"Floor {call.data['floor_id']} not found"
            raise HomeAssistantError(msg)

        area_registry = ar.async_get(self.hass)
        for area_id in call.data["area_id"]:
            area_registry.async_update(
                area_id=area_id,
                floor_id=call.data["floor_id"],
            )
