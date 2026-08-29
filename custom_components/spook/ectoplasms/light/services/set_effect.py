"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_EFFECT,
    ATTR_EFFECT_LIST,
    DOMAIN,
    LightEntity,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService
from .. import async_lights_that_are_on

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[LightEntity]):
    """Light service that sets an effect on what is already lit.

    Only on lights that have the effect asked for. Effect names are per
    manufacturer and rarely agree, so a room is usually a mix of lights that
    know "Colorloop" and lights that have never heard of it.
    """

    domain = DOMAIN
    service = "set_effect"
    schema = {vol.Required(ATTR_EFFECT): cv.string}

    async def async_handle_service(
        self,
        entity: LightEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        effect = call.data[ATTR_EFFECT]

        lights = [
            light
            for light in async_lights_that_are_on(self.hass, entity.entity_id)
            if effect in (light.attributes.get(ATTR_EFFECT_LIST) or ())
        ]
        if not lights:
            return

        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: [light.entity_id for light in lights],
                ATTR_EFFECT: effect,
            },
            blocking=True,
            context=call.context,
        )
