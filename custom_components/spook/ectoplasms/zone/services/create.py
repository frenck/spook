"""Spook - Not your homie."""
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
        collection: ZoneStorageCollection = self.hass.data[DOMAIN]
        await collection.async_create_item(call.data.copy())
