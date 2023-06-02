"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components.homeassistant import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to disable a config entry."""

    domain = DOMAIN
    service = "disable_config_entry"
    schema = {vol.Required("config_entry_id"): cv.string}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        await self.hass.config_entries.async_set_disabled_by(
            call.data["config_entry_id"],
            disabled_by=ConfigEntryDisabler.USER,
        )
