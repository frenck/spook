"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.input_number import (
    CONF_MAX,
    CONF_MIN,
    CONF_STEP,
    DOMAIN,
    InputNumber,
)
from homeassistant.const import CONF_ID
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from ....helper_collections import async_get_storage_collection
from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[InputNumber]):
    """Input number entity service, changing its range: min, max and step.

    The helper as it is stored, the same as editing it in the UI. A value
    that falls outside the new range is moved inside it by Home Assistant.
    """

    domain = DOMAIN
    service = "set_range"
    # This changes the helper as it is stored, which editing it in the UI
    # only lets an admin do. Setting its value is somebody using it, this is
    # somebody changing it.
    admin_only = True
    schema = {
        vol.Optional(CONF_MIN): vol.Coerce(float),
        vol.Optional(CONF_MAX): vol.Coerce(float),
        vol.Optional(CONF_STEP): vol.All(vol.Coerce(float), vol.Range(min=1e-9)),
    }

    async def async_handle_service(
        self,
        entity: InputNumber,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        changes = {
            key: call.data[key]
            for key in (CONF_MIN, CONF_MAX, CONF_STEP)
            if key in call.data
        }
        if not changes:
            message = "Give a minimum, a maximum or a step to change"
            raise ServiceValidationError(message)

        collection = async_get_storage_collection(self.hass, DOMAIN)
        if (
            not entity.editable
            or not (item_id := entity.unique_id)
            or item_id not in collection.data
        ):
            message = f"This input number is not editable: {entity.entity_id}"
            raise HomeAssistantError(message)

        # Home Assistant checks the whole helper when it is updated, so the
        # change goes on top of what is stored, not on its own.
        updates = {**collection.data[item_id], **changes}
        updates.pop(CONF_ID, None)

        try:
            await collection.async_update_item(item_id, updates)
        except vol.Invalid as err:
            # A maximum that is not above the minimum, for example: refused by
            # Home Assistant's own check, and nothing is stored.
            raise ServiceValidationError(str(err)) from err
