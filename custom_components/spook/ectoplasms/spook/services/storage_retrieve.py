"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ....const import DOMAIN
from ....services import AbstractSpookService
from .. import STORAGE_KEY, SpookKeyValueStore

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall, ServiceResponse


class SpookService(AbstractSpookService):
    """Service to retrieve an item form the key/value storage."""

    domain = DOMAIN
    service = "storage_retrieve"
    schema = {
        vol.Required("key"): cv.string,
    }
    supports_response = SupportsResponse.ONLY

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        store: SpookKeyValueStore = self.hass.data[STORAGE_KEY]
        key = call.data["key"]
        try:
            return store.async_retrieve(key)
        except KeyError as err:
            msg = f"Key '{key}' not found in Spook's key/value store."
            raise ServiceValidationError(msg) from err
