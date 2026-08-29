"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

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
    from collections.abc import Coroutine

    from homeassistant.core import ServiceCall, State

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
        transition = call.data.get(ATTR_TRANSITION)

        def _call(light: State) -> Coroutine[Any, Any, Any]:
            """Return the call that steps one light from where it is."""
            brightness = light.attributes[ATTR_BRIGHTNESS] + step
            data: dict[str, Any] = {
                ATTR_ENTITY_ID: light.entity_id,
                ATTR_BRIGHTNESS: min(max(brightness, _DIMMEST), _FULL),
            }

            if transition is not None:
                data[ATTR_TRANSITION] = transition

            return self.hass.services.async_call(
                DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=call.context
            )

        # Every light lands on a different level, so this cannot be one call.
        # Waiting for each in turn can, though: a room full of lights would
        # take as long as all of them added together, and slow ones are
        # exactly what somebody is dimming.
        # A light with no dimmer has no level to step, and it is still a
        # light: it lands in a group and in an area target like any other.
        await asyncio.gather(
            *(
                _call(light)
                for light in async_lights_that_are_on(self.hass, entity.entity_id)
                if light.attributes.get(ATTR_BRIGHTNESS) is not None
            )
        )
