"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import SupportsResponse

from ....const import DOMAIN
from ....services import AbstractSpookService
from .. import STORAGE_KEY, SpookKeyValueStore

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall, ServiceResponse


class SpookService(AbstractSpookService):
    """Service dump all values in the Spook key/value storage."""

    domain = DOMAIN
    service = "storage_dump"
    supports_response = SupportsResponse.ONLY

    async def async_handle_service(self, _: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        store: SpookKeyValueStore = self.hass.data[STORAGE_KEY]
        return store.async_dump()
