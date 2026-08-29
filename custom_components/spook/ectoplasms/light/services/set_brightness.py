"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_TRANSITION,
    DOMAIN,
    LightEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService
from .. import async_lights_that_are_on

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_BRIGHTNESS_PCT = "brightness_pct"


class SpookService(AbstractSpookEntityComponentService[LightEntity]):
    """Light service that sets brightness on what is already lit.

    `light.turn_on` with a brightness does two things at once: it sets the
    level and it switches the light on. Most of the time somebody adjusting a
    room means the first without the second, and there is no way to ask for
    that.
    """

    domain = DOMAIN
    service = "set_brightness"
    schema = {
        vol.Required(CONF_BRIGHTNESS_PCT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(ATTR_TRANSITION): cv.positive_float,
    }

    async def async_handle_service(
        self,
        entity: LightEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        for light in async_lights_that_are_on(self.hass, entity.entity_id):
            data = {
                ATTR_ENTITY_ID: light.entity_id,
                ATTR_BRIGHTNESS_PCT: call.data[CONF_BRIGHTNESS_PCT],
            }

            if (transition := call.data.get(ATTR_TRANSITION)) is not None:
                data[ATTR_TRANSITION] = transition

            await self.hass.services.async_call(
                DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=call.context
            )
