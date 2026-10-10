"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.water_heater import (
    DOMAIN,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)

from ...services import AbstractSpookEntityComponentService
from ...setpoints import STEP_SCHEMA, moved_setpoint, temperature_step

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class AbstractStepTemperatureService(
    AbstractSpookEntityComponentService[WaterHeaterEntity]
):
    """Shared half of stepping a water heater's setpoint up and down.

    The same as for a thermostat, with one setpoint: worked out in the water
    heater's own unit, kept within its limits, and never set through
    `water_heater.set_temperature`, which would wait on the lock this action
    already holds on a platform that does one call at a time.
    """

    domain = DOMAIN
    required_features = [WaterHeaterEntityFeature.TARGET_TEMPERATURE]
    schema = STEP_SCHEMA

    #: Which way this one goes.
    direction: int

    async def async_handle_service(
        self,
        entity: WaterHeaterEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if (target := entity.target_temperature) is None:
            return

        step = self.direction * temperature_step(
            self.hass, call, entity.target_temperature_step, entity.temperature_unit
        )
        moved = moved_setpoint(target, step, entity.min_temp, entity.max_temp)
        if moved is None:
            return

        await entity.async_set_temperature(temperature=moved)
