"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.humidifier import DOMAIN, HumidifierEntity

from ...services import AbstractSpookEntityComponentService
from ...setpoints import CONF_STEP, moved_setpoint, whole_percent

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

# What the Home Assistant interface steps by when a humidifier does not say.
_DEFAULT_STEP = 1


class AbstractStepHumidityService(
    AbstractSpookEntityComponentService[HumidifierEntity]
):
    """Shared half of stepping a humidifier's target humidity up and down.

    The same as for a thermostat, in whole percentages: Home Assistant hands
    a humidifier its target as a whole number. A step of its own that is not
    one, like half a percent, would round to a whole step one time and to no
    step at all the next, so every step is a whole percentage, at least one.
    """

    domain = DOMAIN
    schema = {
        vol.Optional(CONF_STEP): whole_percent,
    }

    #: Which way this one goes.
    direction: int

    async def async_handle_service(
        self,
        entity: HumidifierEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if (target := entity.target_humidity) is None:
            return

        step = call.data.get(CONF_STEP) or entity.target_humidity_step or _DEFAULT_STEP
        step = self.direction * max(round(step), 1)

        moved = moved_setpoint(
            round(target), step, entity.min_humidity, entity.max_humidity
        )
        if moved is None:
            return

        # Straight to the humidifier, not through `humidifier.set_humidity`,
        # which would wait on the lock this action already holds on a
        # platform that does one call at a time.
        await entity.async_set_humidity(round(moved))
