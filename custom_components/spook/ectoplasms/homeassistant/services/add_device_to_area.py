"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
)

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add a device to an area."""

    domain = DOMAIN
    service = "add_device_to_area"
    schema = {
        vol.Required("area_id"): cv.string,
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        area_registry = ar.async_get(self.hass)
        if not area_registry.async_get_area(call.data["area_id"]):
            msg = f"Area {call.data['area_id']} not found"
            raise HomeAssistantError(msg)

        device_registry = dr.async_get(self.hass)
        for device_id in call.data["device_id"]:
            device_registry.async_update_device(
                device_id,
                area_id=call.data["area_id"],
            )
