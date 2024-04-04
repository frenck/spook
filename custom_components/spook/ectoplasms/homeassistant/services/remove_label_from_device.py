"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, device_registry as dr

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to remove a label from a device."""

    domain = DOMAIN
    service = "remove_label_from_device"
    schema = {
        vol.Required("label_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        device_registry = dr.async_get(self.hass)
        for device_id in call.data["device_id"]:
            if device_entry := device_registry.async_get(device_id):
                labels = device_entry.labels.copy()
                labels.difference_update(call.data["label_id"])
                device_registry.async_update_device(device_id, labels=labels)
