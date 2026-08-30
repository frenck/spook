"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, label_registry as lr

from ....services import AbstractSpookAdminService
from ..labels import SUPPORTED_LABEL_THEME_COLORS

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to create labels on the fly."""

    domain = DOMAIN
    service = "create_label"
    schema = {
        vol.Required("name"): cv.string,
        vol.Optional("color"): vol.Any(
            cv.color_hex, vol.In(SUPPORTED_LABEL_THEME_COLORS)
        ),
        vol.Optional("description"): cv.string,
        vol.Optional("icon"): cv.icon,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        label_registry = lr.async_get(self.hass)
        try:
            label_registry.async_create(
                name=call.data["name"],
                color=call.data.get("color"),
                description=call.data.get("description"),
                icon=call.data.get("icon"),
            )
        except ValueError as err:
            # A name another label already has. Left alone this comes back as
            # an unknown error with the registry's own wording.
            raise HomeAssistantError(str(err)) from err
