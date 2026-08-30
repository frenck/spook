"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, label_registry as lr
from homeassistant.helpers.typing import UNDEFINED

from ....services import AbstractSpookAdminService
from ..labels import SUPPORTED_LABEL_THEME_COLORS, async_check_labels_exist

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

_UPDATABLE = ("name", "description", "icon", "color")


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to update a label on the fly.

    Creating a label with a name that already exists makes a second label
    rather than changing the first, so the only way to edit one used to be
    deleting it and starting over. That takes the label off everything it was
    on, which is rarely what somebody wanting a new description had in mind.
    """

    domain = DOMAIN
    service = "update_label"
    schema = {
        vol.Required("label_id"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("color"): vol.Any(
            cv.color_hex, vol.In(SUPPORTED_LABEL_THEME_COLORS)
        ),
        vol.Optional("description"): cv.string,
        vol.Optional("icon"): cv.icon,
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        label_id = call.data["label_id"]
        async_check_labels_exist(self.hass, [label_id])

        # Everything left out keeps the value it has. Without this an
        # unmentioned icon would be read as "remove the icon".
        changes = {
            field: call.data[field] for field in _UPDATABLE if field in call.data
        }

        if not changes:
            msg = (
                f"Nothing to update on label {label_id}: "
                f"give at least one of {', '.join(_UPDATABLE)}"
            )
            raise HomeAssistantError(msg)

        lr.async_get(self.hass).async_update(
            label_id,
            **{field: changes.get(field, UNDEFINED) for field in _UPDATABLE},
        )
