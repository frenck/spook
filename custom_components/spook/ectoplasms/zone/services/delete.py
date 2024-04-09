"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.zone import DOMAIN, Zone, ZoneStorageCollection
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Zone service to delete zones on the fly."""

    domain = DOMAIN
    service = "delete"
    schema = {
        vol.Required("entity_id"): cv.entities_domain(DOMAIN),
    }

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

        for entity_id in call.data["entity_id"]:
            if not (entity := entity_component.get_entity(entity_id)):
                message = f"Could not find entity_id: {entity_id}"
                raise HomeAssistantError(message)

            # pylint: disable-next=protected-access
            if not entity.editable or "id" not in entity._config:  # noqa: SLF001
                message = f"This zone is not editable: {entity_id}"
                raise HomeAssistantError(message)

            # pylint: disable-next=protected-access
            await collection.async_delete_item(entity._config["id"])  # noqa: SLF001
