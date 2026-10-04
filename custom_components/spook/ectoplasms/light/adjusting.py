"""Spook - Your homie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.components.light import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL
from homeassistant.helpers.service import async_extract_entity_ids

from ...services import AbstractSpookService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class AbstractAdjustLightService(AbstractSpookService):
    """Shared half of the actions that adjust lights already on.

    These hand the work on to `light.turn_on`, which does what a light needs
    done first: brightness from percentages, colours a light can show. That
    makes them plain actions that find their own lights, rather than entity
    actions. Home Assistant runs an entity action holding its platform's
    lock, and `light.turn_on` waits for that same lock, so on a platform that
    does one call at a time the two would wait on each other for ever.
    """

    domain = DOMAIN

    async def async_handle_service(self, call: ServiceCall) -> None:
        """Adjust every light the call is aimed at, all at once."""
        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL:
            targets = set(self.hass.states.async_entity_ids(DOMAIN))
        else:
            targets = {
                entity_id
                for entity_id in await async_extract_entity_ids(call)
                if entity_id.startswith(f"{DOMAIN}.")
            }

        await asyncio.gather(
            *(self.async_adjust(entity_id, call) for entity_id in sorted(targets))
        )

    async def async_adjust(self, entity_id: str, call: ServiceCall) -> None:
        """Adjust the lights behind one target."""
        raise NotImplementedError
