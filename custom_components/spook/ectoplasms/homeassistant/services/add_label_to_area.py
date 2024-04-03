"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    label_registry as lr,
)

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add a label to an area."""

    domain = DOMAIN
    service = "add_label_to_area"
    schema = {
        vol.Required("label_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("area_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        label_registry = lr.async_get(self.hass)
        for label_id in call.data["label_id"]:
            if not label_registry.async_get_label(label_id):
                msg = f"Label {label_id} not found"
                raise HomeAssistantError(msg)

        area_registry = ar.async_get(self.hass)
        for area_id in call.data["area_id"]:
            if area_entry := area_registry.async_get_area(area_id):
                labels = area_entry.labels.copy()
                labels.update(call.data["label_id"])
                area_registry.async_update(area_id, labels=labels)
