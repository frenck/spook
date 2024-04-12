"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.zone import (
    DOMAIN,
    UPDATE_FIELDS,
    Zone,
    ZoneStorageCollection,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Zone service to update a zone on the fly."""

    domain = DOMAIN
    service = "update"
    schema = {
        vol.Required("entity_id"): cv.entity_domain(DOMAIN),
    } | UPDATE_FIELDS

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        entity_component: EntityComponent[Zone] = self.hass.data[DATA_INSTANCES][DOMAIN]

        collection: ZoneStorageCollection
        if DOMAIN in self.hass.data:
            collection = self.hass.data[DOMAIN]
        else:
            # Home zone is set in YAML, as a result Home Assistant doesn't
            # set the storage collection into hass data.
            # Major hack to get around this. 👻
            collection = self.hass.data["websocket_api"]["zone/list"][
                0
            ].__self__.storage_collection

        if not (entity := entity_component.get_entity(call.data["entity_id"])):
            message = f"Could not find entity_id: {call.data['entity_id']}"
            raise HomeAssistantError(message)

        # pylint: disable-next=protected-access
        if not entity.editable or "id" not in entity._config:  # noqa: SLF001
            message = f"This zone is not editable: {call.data['entity_id']}"
            raise HomeAssistantError(message)

        data = call.data.copy()
        data.pop("entity_id")

        # pylint: disable-next=protected-access
        await collection.async_update_item(entity._config["id"], data)  # noqa: SLF001
