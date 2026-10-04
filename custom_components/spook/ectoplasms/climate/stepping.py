"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TARGET_TEMP_STEP,
    DOMAIN,
    SERVICE_SET_TEMPERATURE,
    ClimateEntity,
    ClimateEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, UnitOfTemperature

from ...services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_STEP = "step"

# What the Home Assistant interface steps by when a thermostat does not say.
_DEFAULT_STEP = {UnitOfTemperature.CELSIUS: 0.5, UnitOfTemperature.FAHRENHEIT: 1.0}

# Steps like 0.1 add up to 20.600000000000001 in floats, which no thermostat
# wants to be sent. Two decimals is finer than any of them goes.
_DECIMALS = 2


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
    schema = {
        vol.Optional(CONF_STEP): vol.All(
            vol.Coerce(float), vol.Range(min=0, min_included=False)
        ),
    }

    #: Which way this one goes.
    direction: int

    async def async_handle_service(
        self,
        entity: ClimateEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if (state := self.hass.states.get(entity.entity_id)) is None:
            return

        attributes = state.attributes
        step = self.direction * (
            call.data.get(CONF_STEP)
            or attributes.get(ATTR_TARGET_TEMP_STEP)
            or _DEFAULT_STEP[self.hass.config.units.temperature_unit]
        )
        lowest = attributes.get(ATTR_MIN_TEMP)
        highest = attributes.get(ATTR_MAX_TEMP)

        changes: dict[str, Any]
        if (target := attributes.get(ATTR_TEMPERATURE)) is not None:
            moved = _within(target + step, lowest, highest)
            if not self._goes_our_way(moved - target):
                return
            changes = {ATTR_TEMPERATURE: moved}

        elif (low := attributes.get(ATTR_TARGET_TEMP_LOW)) is not None and (
            high := attributes.get(ATTR_TARGET_TEMP_HIGH)
        ) is not None:
            # Both move by the same amount, so the band between them keeps
            # its width. One that reaches its limit stops the other too:
            # squeezing the band against a limit would leave a thermostat
            # heating and cooling a degree apart.
            if highest is not None:
                step = min(step, highest - high)
            if lowest is not None:
                step = max(step, lowest - low)
            if not self._goes_our_way(step):
                return
            changes = {
                ATTR_TARGET_TEMP_LOW: round(low + step, _DECIMALS),
                ATTR_TARGET_TEMP_HIGH: round(high + step, _DECIMALS),
            }

        else:
            # No setpoint to move: a thermostat in a mode without one, like
            # fan only, or one that has not reported yet.
            return

        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity.entity_id, **changes},
            blocking=True,
            context=call.context,
        )

    def _goes_our_way(self, change: float) -> bool:
        """Return whether a change is a step in the asked direction.

        Not just whether it is a change: a thermostat already past one of
        its limits, which some integrations report, would be pulled back to
        it, and "warmer" would make it colder.
        """
        return change * self.direction > 0


def _within(value: float, lowest: float | None, highest: float | None) -> float:
    """Return the value, kept between the limits that are known."""
    if highest is not None:
        value = min(value, highest)
    if lowest is not None:
        value = max(value, lowest)
    return round(value, _DECIMALS)
