"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
)

from ....const import DOMAIN as SPOOK_DOMAIN
from ....core_compat import async_update_any_device
from ....errors import area_not_found, device_not_found
from ....services import AbstractSpookAdminService
from ..device import (
    async_disable_device_and_parent_if_needed,
    async_enable_device_and_parent,
)
from ..labels import async_check_labels_exist

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

_UPDATABLE = ("name_by_user", "area_id", "labels", "disabled_by")


class SpookService(AbstractSpookAdminService):
    """Home Assistant service to update a device on the fly.

    Only what a user can change in the UI is offered. Everything else on a
    device belongs to the integration that made it, and it would write its
    own values back over the next time it sets up.
    """

    domain = DOMAIN
    service = "update_device"
    schema = {
        vol.Required("device_id"): cv.string,
        # `None` clears these, which is why they are not plain validators.
        # Clearing the name gives the device its name from the integration
        # back, clearing the area takes it out of its area.
        vol.Optional("name_by_user"): vol.Any(None, cv.string),
        vol.Optional("area_id"): vol.Any(None, cv.string),
        # Labels replace what the device has, like the UI does. An empty list
        # clears them.
        vol.Optional("labels"): vol.All(cv.ensure_list, [cv.string]),
        # A user can only disable a device as a user, like in the UI. The
        # other reasons are Home Assistant's to set.
        vol.Optional("disabled_by"): vol.Any(
            None, vol.In([dr.DeviceEntryDisabler.USER.value])
        ),
    }

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Handle the service call."""
        device_id = call.data["device_id"]
        device_registry = dr.async_get(self.hass)
        if device_registry.async_get(device_id) is None:
            raise device_not_found(device_id)

        # Left out means keep, `None` means clear. Passing everything through
        # would turn an unmentioned area into "take it out of its area".
        changes = {
            field: call.data[field] for field in _UPDATABLE if field in call.data
        }

        if not changes:
            raise HomeAssistantError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="device_nothing_to_update",
                translation_placeholders={
                    "device_id": device_id,
                    "fields": ", ".join(_UPDATABLE),
                },
            )

        # The registry stores an area or label that does not exist without a
        # word. Checked before anything is written, so a refused call changes
        # nothing.
        area_id = changes.get("area_id")
        if area_id is not None and not ar.async_get(self.hass).async_get_area(area_id):
            raise area_not_found(area_id)

        if "labels" in changes:
            changes["labels"] = set(changes["labels"])
            async_check_labels_exist(self.hass, changes["labels"])

        if registry_changes := {
            field: value for field, value in changes.items() if field != "disabled_by"
        }:
            async_update_any_device(device_registry, device_id, **registry_changes)

        # Disabling and enabling go the way disable_device and enable_device
        # go. Home Assistant will not enable a child device while its parent
        # is disabled, so the parent comes along, and a parent left with
        # nothing enabled hanging off it is disabled too.
        if "disabled_by" not in changes:
            return

        if changes["disabled_by"] is None:
            async_enable_device_and_parent(device_registry, device_id)
        else:
            async_disable_device_and_parent_if_needed(device_registry, device_id)
