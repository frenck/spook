"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
)

from ....errors import entity_not_found
from ....services import AbstractSpookAdminService
from ..labels import async_check_labels_exist

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to remove a label from an entity."""

    domain = DOMAIN
    service = "remove_label_from_entity"
    schema = {
        vol.Required("label_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("entity_id"): vol.All(cv.ensure_list, [cv.string]),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        async_check_labels_exist(self.hass, call.data["label_id"])

        entity_registry = er.async_get(self.hass)

        # Everything is looked up before anything is written. A typo in the
        # last one should not leave the first ones changed behind an error.
        updates: dict[str, set[str]] = {}
        for entity_id in call.data["entity_id"]:
            if (entity_entry := entity_registry.async_get(entity_id)) is None:
                raise entity_not_found(entity_id)

            labels = entity_entry.labels.copy()
            labels.difference_update(call.data["label_id"])
            updates[entity_id] = labels

        for entity_id, labels in updates.items():
            entity_registry.async_update_entity(entity_id, labels=labels)
