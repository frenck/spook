"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    DOMAIN,
    LightEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.helpers import config_validation as cv

from ...services import AbstractSpookEntityComponentService
from . import async_lights_that_are_on

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_STEP_PCT = "step_pct"

# Full brightness in the numbers the light platform actually uses.
_FULL = 255

# One, not zero, because zero is off and these actions do not switch lights.
_DIMMEST = 1


class AbstractStepBrightnessService(AbstractSpookEntityComponentService[LightEntity]):
    """Shared half of stepping brightness up and down.

    The whole point is doing it per light. Stepping a group entity has Home
    Assistant average its members, apply the step to that average, and then
    set every member to the result, so a room with one lamp at 10% and one at
    100% ends up with both at 65% after asking for a little more light.
    """

    domain = DOMAIN
    schema = {
        vol.Required(CONF_STEP_PCT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional(ATTR_TRANSITION): cv.positive_float,
    }

    #: Which way this one goes.
    direction: int

    async def async_handle_service(
        self,
        entity: LightEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        step = round(_FULL * call.data[CONF_STEP_PCT] / 100) * self.direction

        for light in async_lights_that_are_on(self.hass, entity.entity_id):
            brightness = light.attributes[ATTR_BRIGHTNESS] + step
            data = {
                ATTR_ENTITY_ID: light.entity_id,
                ATTR_BRIGHTNESS: min(max(brightness, _DIMMEST), _FULL),
            }

            if (transition := call.data.get(ATTR_TRANSITION)) is not None:
                data[ATTR_TRANSITION] = transition

            await self.hass.services.async_call(
                DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=call.context
            )
