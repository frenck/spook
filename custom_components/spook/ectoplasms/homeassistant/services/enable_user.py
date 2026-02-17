"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant Core integration service to enable a user."""

    domain = DOMAIN
    service = "enable_user"
    schema = {vol.Required("user_id"): vol.All(cv.ensure_list, [cv.string])}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        for user_id in call.data["user_id"]:
            user = await self.hass.auth.async_get_user(user_id)
            if user is None:
                message = f"Could not find user: {user_id}"
                raise HomeAssistantError(message)
            await self.hass.auth.async_update_user(user, is_active=True)
