"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE

from ...services import AbstractSpookEntityComponentService
from ...setpoints import STEP_SCHEMA, moved_band, moved_setpoint, temperature_step

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class AbstractStepTemperatureService(
    AbstractSpookEntityComponentService[ClimateEntity]
):
    """Shared half of stepping a thermostat's setpoint up and down.

    Home Assistant only knows setting a temperature, so a "one warmer" button
    has to read the setpoint, add to it, and send it back, in a template
    nobody gets right on the first try for a thermostat with two setpoints.

    Adjusting is not switching: a thermostat that is off gets its setpoint
    moved and stays off, the way the Home Assistant interface does it.
    """

    domain = DOMAIN
    required_features = [
        ClimateEntityFeature.TARGET_TEMPERATURE,
        ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
    ]
    schema = STEP_SCHEMA

    #: Which way this one goes.
    direction: int

    async def async_handle_service(
        self,
        entity: ClimateEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call.

        Worked out in the thermostat's own unit, from the thermostat itself.
        Home Assistant shows its temperatures in Home Assistant's unit,
        rounded, and turning those back would send 69.008 degrees Fahrenheit
        for a step from 68, or a minimum of 45 as 44.996, just past a limit
        the thermostat may well refuse. A step given in the call is in Home
        Assistant's unit, and is the one thing turned into the thermostat's.
        """
        step = self.direction * temperature_step(
            self.hass, call, entity.target_temperature_step, entity.temperature_unit
        )

        lowest = entity.min_temp
        highest = entity.max_temp

        # Read only what the thermostat says it has, the way Home Assistant
        # does: a thermostat without a band need not have its setpoints at
        # all, and asking for them raises rather than answering nothing.
        features = entity.supported_features
        target = (
            entity.target_temperature
            if features & ClimateEntityFeature.TARGET_TEMPERATURE
            else None
        )
        low = high = None
        if features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE:
            low = entity.target_temperature_low
            high = entity.target_temperature_high

        changes: dict[str, Any] = {}
        # Heating and cooling to a band is what a thermostat does in
        # `heat_cool`, even one that reports a single setpoint as well.
        if (
            low is not None
            and high is not None
            and (target is None or entity.hvac_mode == HVACMode.HEAT_COOL)
        ):
            if band := moved_band(low, high, step, lowest, highest):
                changes = {
                    ATTR_TARGET_TEMP_LOW: band[0],
                    ATTR_TARGET_TEMP_HIGH: band[1],
                }
        elif target is not None:
            if (moved := moved_setpoint(target, step, lowest, highest)) is not None:
                changes = {ATTR_TEMPERATURE: moved}
        else:
            # No setpoint to move: a thermostat in a mode without one, like
            # fan only, or one that has not reported yet.
            return

        if not changes:
            return

        # Straight to the thermostat, not through `climate.set_temperature`.
        # This action already holds the platform's lock for this thermostat,
        # and on a platform that does one call at a time, that action would
        # wait for it for ever.
        await entity.async_set_temperature(**changes)
