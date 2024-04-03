"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import config_validation as cv, label_registry as lr

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

SUPPORTED_LABEL_THEME_COLORS = {
    "primary",
    "accent",
    "disabled",
    "amber",
    "black",
    "blue-grey",
    "blue",
    "brown",
    "cyan",
    "dark-grey",
    "deep-orange",
    "deep-purple",
    "green",
    "grey",
    "indigo",
    "light-blue",
    "light-green",
    "light-grey",
    "lime",
    "orange",
    "pink",
    "purple",
    "red",
    "teal",
    "white",
    "yellow",
}


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
        label_registry.async_create(
            name=call.data["name"],
            color=call.data.get("color"),
            description=call.data.get("description"),
            icon=call.data.get("icon"),
        )
