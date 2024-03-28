"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from ....const import DOMAIN
from ....services import AbstractSpookAdminService
from .. import STORAGE_KEY, SpookKeyValueStore

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Service to delete a value from the Spook key/value storage."""

    domain = DOMAIN
    service = "storage_delete"
    schema = {
        vol.Required("key"): cv.string,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        store: SpookKeyValueStore = self.hass.data[STORAGE_KEY]
        store.async_delete(call.data["key"])
