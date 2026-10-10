"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
)

from ....errors import area_not_found
from ....services import AbstractSpookAdminService
from ..labels import async_check_labels_exist

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
        async_check_labels_exist(self.hass, call.data["label_id"])

        area_registry = ar.async_get(self.hass)

        # Everything is looked up before anything is written. A typo in the
        # last one should not leave the first ones changed behind an error.
        updates: dict[str, set[str]] = {}
        for area_id in call.data["area_id"]:
            if (area_entry := area_registry.async_get_area(area_id)) is None:
                raise area_not_found(area_id)

            labels = area_entry.labels.copy()
            labels.update(call.data["label_id"])
            updates[area_id] = labels

        for area_id, labels in updates.items():
            area_registry.async_update(area_id, labels=labels)
