"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN,
    CoverEntity,
    CoverEntityFeature,
)

from ...services import AbstractSpookEntityComponentService
from ...setpoints import CONF_STEP, moved_setpoint, whole_number

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

# A cover does not say how far one step is, the way a thermostat does, so
# this is a guess at what "a bit further" means for a blind.
_DEFAULT_STEP = 10

_CLOSED = 0
_OPEN = 100


class AbstractStepPositionService(AbstractSpookEntityComponentService[CoverEntity]):
    """Shared half of stepping a cover's position open or closed.

    Home Assistant only knows setting a position, so "a bit further open" has
    to read the position, add to it, and send it back. Positions are whole
    percentages, from 0 for closed to 100 for open.
    """

    domain = DOMAIN
    required_features = [CoverEntityFeature.SET_POSITION]
    schema = {
        vol.Optional(CONF_STEP, default=_DEFAULT_STEP): vol.All(
            whole_number, vol.Range(min=1, max=100)
        ),
    }

    #: Which way this one goes: towards open, or towards closed.
    direction: int

    async def async_handle_service(
        self,
        entity: CoverEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if (position := entity.current_cover_position) is None:
            return

        moved = moved_setpoint(
            position, self.direction * call.data[CONF_STEP], _CLOSED, _OPEN
        )
        if moved is None:
            return

        # Straight to the cover, not through `cover.set_cover_position`,
        # which would wait on the lock this action already holds on a
        # platform that does one call at a time. That action hands the
        # position over as it is, so nothing is lost by skipping it.
        await entity.async_set_cover_position(**{ATTR_POSITION: round(moved)})
