"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv

from ....errors import config_entry_not_found
from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to disable polling."""

    domain = DOMAIN
    service = "disable_polling"
    schema = {vol.Required("config_entry_id"): cv.string}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        if not (
            entry := self.hass.config_entries.async_get_entry(
                call.data["config_entry_id"],
            )
        ):
            raise config_entry_not_found(call.data["config_entry_id"])

        self.hass.config_entries.async_update_entry(
            entry,
            pref_disable_polling=True,
        )
