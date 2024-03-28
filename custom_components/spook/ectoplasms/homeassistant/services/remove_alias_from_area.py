"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar, config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to remove an alias to an area."""

    domain = DOMAIN
    service = "remove_alias_from_area"
    schema = {
        vol.Required("area_id"): cv.string,
        vol.Required("alias"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        area_registry = ar.async_get(self.hass)
        if not (area := area_registry.async_get_area(call.data["area_id"])):
            msg = f"Area {call.data['area_id']} not found"
            raise HomeAssistantError(msg)

        aliases = area.aliases.copy()
        area_registry.async_update(
            call.data["area_id"],
            aliases=aliases.difference(call.data["alias"]),
        )
