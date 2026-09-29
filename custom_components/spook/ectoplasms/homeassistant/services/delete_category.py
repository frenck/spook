"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.helpers import category_registry as cr, config_validation as cv

from ....services import AbstractSpookAdminService
from ..categories import SCOPES, async_resolve_category

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to delete a category on the fly.

    Home Assistant takes a deleted category off everything that had it, so
    there is nothing left to clean up afterwards.
    """

    domain = DOMAIN
    service = "delete_category"
    schema = {
        vol.Required("scope"): vol.In(SCOPES),
        vol.Required("category_id"): cv.string,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        scope = call.data["scope"]
        category = async_resolve_category(self.hass, scope, call.data["category_id"])
        cr.async_get(self.hass).async_delete(
            scope=scope, category_id=category.category_id
        )
