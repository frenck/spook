"""Spook - Not your homie."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv

from . import AbstractSpookAdminService


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to enable a config entry."""

    domain = DOMAIN
    service = "enable_config_entry"
    schema = {vol.Required("config_entry_id"): cv.string}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        await self.hass.config_entries.async_set_disabled_by(
            call.data["config_entry_id"],
            disabled_by=None,
        )
