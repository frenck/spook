"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.core import ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import category_registry as cr, config_validation as cv

from ....services import AbstractSpookAdminService
from ..categories import SCOPES

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to create categories on the fly.

    A category's ID is random, unlike a label's, so it comes back in the
    response. Otherwise an automation could make one and never use it.
    """

    domain = DOMAIN
    service = "create_category"
    schema = {
        vol.Required("scope"): vol.In(SCOPES),
        vol.Required("name"): cv.string,
        vol.Optional("icon"): cv.icon,
    }
    supports_response = SupportsResponse.OPTIONAL

    async def async_handle_service(self, call: ServiceCall) -> ServiceResponse:
        """Handle the service call."""
        try:
            category = cr.async_get(self.hass).async_create(
                scope=call.data["scope"],
                name=call.data["name"],
                icon=call.data.get("icon"),
            )
        except ValueError as err:
            # A name another category in this scope already has. Left alone
            # this comes back as an unknown error with the registry's wording.
            raise HomeAssistantError(str(err)) from err

        if call.return_response:
            return {"category_id": category.category_id}
        return None
