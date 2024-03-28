"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.const import RESTART_EXIT_CODE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ....const import LOGGER
from ....services import AbstractSpookAdminService, ReplaceExistingService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService, ReplaceExistingService):
    """Home Assistant service to restart Home Assistant.

    It overrides the built-in restart service to add a force option.
    """

    domain = DOMAIN
    service = "restart"
    schema = {
        vol.Optional("safe_mode", default=False): cv.boolean,
        vol.Optional("force", default=False): cv.boolean,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        if call.data["force"]:
            LOGGER.warning("!! Forcing an Home Assistant restart !!")
            self.hass.data["homeassistant_stop"] = asyncio.create_task(
                self.hass.async_stop(RESTART_EXIT_CODE),
            )
            return

        if not self.overriden_service:
            msg = "Spook encountered an error while restarting Home Assistant."
            raise HomeAssistantError(
                msg,
            )

        self.hass.async_run_hass_job(self.overriden_service.job, call)
