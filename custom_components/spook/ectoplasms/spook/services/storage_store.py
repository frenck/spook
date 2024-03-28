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
    """Service to store a value in the Spook key/value storage."""

    domain = DOMAIN
    service = "storage_store"
    schema = {
        vol.Required("key"): cv.string,
        vol.Required("value"): cv.match_all,
        vol.Optional("is_persistent"): cv.boolean,
        vol.Optional("ttl"): cv.time_period,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        store: SpookKeyValueStore = self.hass.data[STORAGE_KEY]
        data = call.data.copy()
        if "ttl" in call.data:
            data["ttl"] = call.data["ttl"].total_seconds()
        store.async_store(**data)
