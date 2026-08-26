"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, device_registry as dr

from ....core_compat import async_update_any_device
from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to remove a device from an area."""

    domain = DOMAIN
    service = "remove_device_from_area"
    schema = {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        device_registry = dr.async_get(self.hass)
        for device_id in call.data["device_id"]:
            async_update_any_device(
                device_registry,
                device_id,
                area_id=None,
            )
