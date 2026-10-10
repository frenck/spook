"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.zone import CREATE_FIELDS, DOMAIN, ZoneStorageCollection

from ....helper_collections import async_get_storage_collection
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
        collection: ZoneStorageCollection = async_get_storage_collection(
            self.hass, DOMAIN
        )

        await collection.async_create_item(call.data.copy())
