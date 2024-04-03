"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    label_registry as lr,
)

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add a label to a device."""

    domain = DOMAIN
    service = "add_label_to_device"
    schema = {
        vol.Required("label_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        label_registry = lr.async_get(self.hass)
        for label_id in call.data["label_id"]:
            if not label_registry.async_get_label(label_id):
                msg = f"Label {label_id} not found"
                raise HomeAssistantError(msg)

        device_registry = dr.async_get(self.hass)
        for device_id in call.data["device_id"]:
            if device_entry := device_registry.async_get(device_id):
                labels = device_entry.labels.copy()
                labels.update(call.data["label_id"])
                device_registry.async_update_device(device_id, labels=labels)
