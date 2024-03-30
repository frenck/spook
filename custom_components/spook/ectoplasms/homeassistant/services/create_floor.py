"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, floor_registry as fr

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant floor service to create floors on the fly."""

    domain = DOMAIN
    service = "create_floor"
    schema = {
        vol.Required("name"): cv.string,
        vol.Optional("aliases"): [cv.string],
        vol.Optional("icon"): cv.icon,
        vol.Optional("level"): vol.Coerce(int),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        floor_registry = fr.async_get(self.hass)
        floor_registry.async_create(
            name=call.data["name"],
            aliases=call.data.get("aliases"),
            icon=call.data.get("icon"),
            level=call.data.get("level"),
        )
