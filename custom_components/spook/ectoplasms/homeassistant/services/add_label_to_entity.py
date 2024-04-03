"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    label_registry as lr,
)

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to add a label to an entity."""

    domain = DOMAIN
    service = "add_label_to_entity"
    schema = {
        vol.Required("label_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        label_registry = lr.async_get(self.hass)
        for label_id in call.data["label_id"]:
            if not label_registry.async_get_label(label_id):
                msg = f"Label {label_id} not found"
                raise HomeAssistantError(msg)

        entity_registry = er.async_get(self.hass)
        for entity_id in call.data["entity_id"]:
            if entity_entry := entity_registry.async_get(entity_id):
                labels = entity_entry.labels.copy()
                labels.update(call.data["label_id"])
                entity_registry.async_update_entity(entity_id, labels=labels)
