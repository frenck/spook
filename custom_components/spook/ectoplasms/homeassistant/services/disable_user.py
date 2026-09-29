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
    """Home Assistant Core integration service to disable a user."""

    domain = DOMAIN
    service = "disable_user"
    schema = {vol.Required("user_id"): vol.All(cv.ensure_list, [cv.string])}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        # Everything is looked up before anything is written. A bad one late
        # in the list should not leave the first ones changed behind an error.
        users = []
        for user_id in call.data["user_id"]:
            user = await self.hass.auth.async_get_user(user_id)
            if user is None:
                message = f"Could not find user: {user_id}"
                raise HomeAssistantError(message)
            if user.system_generated:
                message = f"Cannot disable a system-generated user: {user_id}"
                raise HomeAssistantError(message)
            users.append(user)

        for user in users:
            await self.hass.auth.async_update_user(user, is_active=False)
