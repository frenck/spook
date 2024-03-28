"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import area_registry as ar, config_validation as cv

from ....services import AbstractSpookAdminService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant area service to delete areas on the fly."""

    domain = DOMAIN
    service = "delete_area"
    schema = {vol.Required("area_id"): cv.string}

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        area_registry = ar.async_get(self.hass)
        area_registry.async_delete(call.data["area_id"])
