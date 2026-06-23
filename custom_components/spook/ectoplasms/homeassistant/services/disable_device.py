"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, device_registry as dr

from ....services import AbstractSpookAdminService
from ..device import async_disable_device_and_parent_if_needed

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to disable a device."""

    domain = DOMAIN
    service = "disable_device"
    schema = {vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string])}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        device_registry = dr.async_get(self.hass)
        for device_id in call.data["device_id"]:
            async_disable_device_and_parent_if_needed(device_registry, device_id)
