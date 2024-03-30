"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, floor_registry as fr

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to set the aliases of a floor."""

    domain = DOMAIN
    service = "set_floor_aliases"
    schema = {
        vol.Required("floor_id"): cv.string,
        vol.Required("aliases"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        floor_registry = fr.async_get(self.hass)
        if not floor_registry.async_get_floor(call.data["floor_id"]):
            msg = f"Floor {call.data['floor_id']} not found"
            raise HomeAssistantError(msg)

        floor_registry.async_update(
            call.data["floor_id"],
            aliases=set(call.data["aliases"]),
        )
