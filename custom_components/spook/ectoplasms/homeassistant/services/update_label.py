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

    Home Assistant can edit a label in the UI, but nothing could do it from an
    automation. Creating one with a name that is already taken is refused, so
    the only way through was to delete the label and make it again. Deleting
    takes it off everything it was on, which is a lot to lose over a
    description.
    """

    domain = DOMAIN
    service = "update_label"
    schema = {
        vol.Required("label_id"): cv.string,
        vol.Optional("name"): cv.string,
        # `None` clears these, which is why they are not plain validators.
        vol.Optional("color"): vol.Any(
            None, cv.color_hex, vol.In(SUPPORTED_LABEL_THEME_COLORS)
        ),
        vol.Optional("description"): vol.Any(None, cv.string),
        vol.Optional("icon"): vol.Any(None, cv.icon),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        label_id = call.data["label_id"]
        async_check_labels_exist(self.hass, [label_id])

        # Left out means keep, `None` means clear. Passing everything through
        # would turn an unmentioned icon into "remove the icon".
        changes = {
            field: call.data[field] for field in _UPDATABLE if field in call.data
        }

        if not changes:
            msg = (
                f"Nothing to update on label {label_id}: "
                f"give at least one of {', '.join(_UPDATABLE)}"
            )
            raise HomeAssistantError(msg)

        try:
            lr.async_get(self.hass).async_update(
                label_id,
                **{field: changes.get(field, UNDEFINED) for field in _UPDATABLE},
            )
        except ValueError as err:
            # Renaming onto a name another label already has. Left alone this
            # comes back as an unknown error with the registry's own wording.
            raise HomeAssistantError(str(err)) from err
