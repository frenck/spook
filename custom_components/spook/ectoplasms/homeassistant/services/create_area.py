"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import area_registry as ar, config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant area service to create areas on the fly."""

    domain = DOMAIN
    service = "create_area"
    schema = {
        vol.Required("name"): cv.string,
        vol.Optional("aliases"): [cv.string],
        vol.Optional("icon"): cv.icon,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        area_registry = ar.async_get(self.hass)
        area_registry.async_create(
            name=call.data["name"],
            aliases=call.data.get("aliases"),
            icon=call.data.get("icon"),
        )
