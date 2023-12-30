"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ....const import DOMAIN
from ....services import AbstractSpookAdminService
from .. import STORAGE_KEY, SpookKeyValueStore

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Service to flush all stored key/values from the Spook key/value storage."""

    domain = DOMAIN
    service = "storage_flush"

    async def async_handle_service(self, _: ServiceCall) -> None:
        """Handle the service call."""
        store: SpookKeyValueStore = self.hass.data[STORAGE_KEY]
        store.async_flush()
