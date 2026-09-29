"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import category_registry as cr, config_validation as cv
from homeassistant.helpers.typing import UNDEFINED

from ....services import AbstractSpookAdminService
from ..categories import SCOPES, async_resolve_category

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

_UPDATABLE = ("name", "icon")


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to update a category on the fly.

    Deleting and creating it again would take it off everything it was on,
    which is a lot to lose over an icon.
    """

    domain = DOMAIN
    service = "update_category"
    schema = {
        vol.Required("scope"): vol.In(SCOPES),
        vol.Required("category_id"): cv.string,
        vol.Optional("name"): cv.string,
        # `None` clears the icon, which is why it is not a plain validator.
        vol.Optional("icon"): vol.Any(None, cv.icon),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        scope = call.data["scope"]
        category = async_resolve_category(self.hass, scope, call.data["category_id"])

        # Left out means keep, `None` means clear. Passing everything through
        # would turn an unmentioned icon into "remove the icon".
        changes = {
            field: call.data[field] for field in _UPDATABLE if field in call.data
        }

        if not changes:
            msg = (
                f"Nothing to update on category {category.name}: "
                f"give at least one of {', '.join(_UPDATABLE)}"
            )
            raise HomeAssistantError(msg)

        try:
            cr.async_get(self.hass).async_update(
                scope=scope,
                category_id=category.category_id,
                **{field: changes.get(field, UNDEFINED) for field in _UPDATABLE},
            )
        except ValueError as err:
            # Renaming onto a name another category in this scope already has.
            raise HomeAssistantError(str(err)) from err
