"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.zone import CREATE_FIELDS, DOMAIN, ZoneStorageCollection

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Zone service to create zones on the fly."""

    domain = DOMAIN
    service = "create"
    schema = CREATE_FIELDS

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
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

        await collection.async_create_item(call.data.copy())
