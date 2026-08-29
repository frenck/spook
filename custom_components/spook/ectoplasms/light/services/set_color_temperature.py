"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    DOMAIN,
    LightEntity,
    color_temp_supported,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService
from .. import async_lights_that_are_on

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from homeassistant.core import ServiceCall, State

CONF_KELVIN = "kelvin"


class SpookService(AbstractSpookEntityComponentService[LightEntity]):
    """Light service that sets colour temperature on what is already lit.

    Kept inside each light's own range, because warm white on one lamp is a
    number another one cannot reach, and a group is rarely all the same model.
    """

    domain = DOMAIN
    service = "set_color_temperature"
    schema = {
        vol.Required(CONF_KELVIN): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Optional(ATTR_TRANSITION): cv.positive_float,
    }

    async def async_handle_service(
        self,
        entity: LightEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        kelvin = call.data[CONF_KELVIN]
        transition = call.data.get(ATTR_TRANSITION)

        def _call(light: State) -> Coroutine[Any, Any, Any]:
            """Return the call that sets one light, within what it can do."""
            coolest = light.attributes.get(ATTR_MAX_COLOR_TEMP_KELVIN, kelvin)
            warmest = light.attributes.get(ATTR_MIN_COLOR_TEMP_KELVIN, kelvin)

            data: dict[str, Any] = {
                ATTR_ENTITY_ID: light.entity_id,
                ATTR_COLOR_TEMP_KELVIN: min(max(kelvin, warmest), coolest),
            }

            if transition is not None:
                data[ATTR_TRANSITION] = transition

            return self.hass.services.async_call(
                DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=call.context
            )

        # One call each, since each light is held to its own range, and all at
        # once, since waiting for them in turn adds up over a room.
        await asyncio.gather(
            *(
                _call(light)
                for light in async_lights_that_are_on(self.hass, entity.entity_id)
                if color_temp_supported(
                    light.attributes.get(ATTR_SUPPORTED_COLOR_MODES)
                )
            )
        )
