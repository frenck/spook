"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
)

from ....core_compat import async_update_any_device
from ....errors import device_not_found
from ....services import AbstractSpookAdminService
from ..labels import async_check_labels_exist

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
        async_check_labels_exist(self.hass, call.data["label_id"])

        device_registry = dr.async_get(self.hass)

        # Everything is looked up before anything is written. A typo in the
        # last one should not leave the first ones changed behind an error.
        updates: dict[str, set[str]] = {}
        for device_id in call.data["device_id"]:
            if (device_entry := device_registry.async_get(device_id)) is None:
                raise device_not_found(device_id)

            labels = device_entry.labels.copy()
            labels.update(call.data["label_id"])
            updates[device_id] = labels

        for device_id, labels in updates.items():
            async_update_any_device(device_registry, device_id, labels=labels)
