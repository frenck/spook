"""Spook - Your homie."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

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


def _finite(value: Any) -> float:
    """Validate a number that is an actual number.

    `float` takes "inf" and "nan" happily, and Home Assistant stores those as
    nothing, which leaves a helper with a range it cannot load again.
    """
    number = float(vol.Coerce(float)(value))
    if not math.isfinite(number):
        message = "The range has to be made of finite numbers"
        raise vol.Invalid(message)
    return number


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
        vol.Optional(CONF_MIN): _finite,
        vol.Optional(CONF_MAX): _finite,
        vol.Optional(CONF_STEP): vol.All(_finite, vol.Range(min=1e-9)),
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

        # Home Assistant checks this too, but which library raises for it
        # differs between versions, so it is checked here first, and said
        # plainly.
        if updates[CONF_MAX] <= updates[CONF_MIN]:
            message = (
                f"The maximum ({updates[CONF_MAX]}) has to be above "
                f"the minimum ({updates[CONF_MIN]})"
            )
            raise ServiceValidationError(message)

        try:
            await collection.async_update_item(item_id, updates)
        except vol.Invalid as err:
            # Anything else Home Assistant's own check refuses, with nothing
            # stored.
            raise ServiceValidationError(str(err)) from err
