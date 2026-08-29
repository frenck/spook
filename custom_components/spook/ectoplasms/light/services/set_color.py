"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_COLOR_NAME,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_TRANSITION,
    DOMAIN,
    LightEntity,
    color_supported,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService
from .. import async_lights_that_are_on

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[LightEntity]):
    """Light service that colours what is already lit.

    Lights that cannot do colour are passed over rather than turned on white,
    which is what `light.turn_on` with a colour does to them.
    """

    domain = DOMAIN
    service = "set_color"
    schema = {
        vol.Exclusive(ATTR_RGB_COLOR, "colour"): vol.All(
            vol.Length(min=3, max=3), [vol.All(vol.Coerce(int), vol.Range(0, 255))]
        ),
        vol.Exclusive(ATTR_COLOR_NAME, "colour"): cv.string,
        vol.Optional(ATTR_TRANSITION): cv.positive_float,
    }

    async def async_handle_service(
        self,
        entity: LightEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if not (call.data.keys() & {ATTR_RGB_COLOR, ATTR_COLOR_NAME}):
            # Checked here rather than in the schema: an entity service takes
            # a plain field mapping, so there is nowhere in it to say that one
            # of two optional keys has to be there.
            msg = f"Set what colour, {ATTR_RGB_COLOR} or {ATTR_COLOR_NAME}?"
            raise ServiceValidationError(msg)

        lights = [
            light
            for light in async_lights_that_are_on(self.hass, entity.entity_id)
            if color_supported(light.attributes.get(ATTR_SUPPORTED_COLOR_MODES))
        ]
        if not lights:
            return

        data: dict[str, object] = {
            ATTR_ENTITY_ID: [light.entity_id for light in lights]
        }

        for key in (ATTR_RGB_COLOR, ATTR_COLOR_NAME, ATTR_TRANSITION):
            if key in call.data:
                data[key] = call.data[key]

        await self.hass.services.async_call(
            DOMAIN, SERVICE_TURN_ON, data, blocking=True, context=call.context
        )
