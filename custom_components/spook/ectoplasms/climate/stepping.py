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
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.util.unit_conversion import TemperatureConverter

from ...services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from collections.abc import Mapping

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
        unit = self.hass.config.units.temperature_unit
        step = self.direction * (
            call.data.get(CONF_STEP)
            or self._own_step(entity, attributes, unit)
            or _DEFAULT_STEP[unit]
        )
        lowest = attributes.get(ATTR_MIN_TEMP)
        highest = attributes.get(ATTR_MAX_TEMP)

        target = attributes.get(ATTR_TEMPERATURE)
        low = attributes.get(ATTR_TARGET_TEMP_LOW)
        high = attributes.get(ATTR_TARGET_TEMP_HIGH)

        changes: dict[str, Any] | None
        # Heating and cooling to a band is what a thermostat does in
        # `heat_cool`, even one that reports a single setpoint as well.
        if (
            low is not None
            and high is not None
            and (target is None or state.state == HVACMode.HEAT_COOL)
        ):
            changes = _moved_band(low, high, step, lowest, highest)
        elif target is not None:
            changes = _moved_setpoint(target, step, lowest, highest)
        else:
            # No setpoint to move: a thermostat in a mode without one, like
            # fan only, or one that has not reported yet.
            return

        if not changes:
            return

        # Straight to the thermostat, not through `climate.set_temperature`.
        # This action already holds the platform's lock for this thermostat,
        # and on a platform that does one call at a time, that action would
        # wait for it for ever. What that action adds is turning the values
        # into the thermostat's own unit, which is done here instead.
        await entity.async_set_temperature(
            **{
                key: TemperatureConverter.convert(value, unit, entity.temperature_unit)
                for key, value in changes.items()
            }
        )

    @staticmethod
    def _own_step(
        entity: ClimateEntity, attributes: Mapping[str, Any], unit: str
    ) -> float | None:
        """Return the thermostat's own step, in Home Assistant's unit.

        Home Assistant shows every temperature of a thermostat in its own
        unit, except the step, which stays in the thermostat's. A step of one
        degree Fahrenheit, read as one degree Celsius, would be nearly two.
        """
        if (step := attributes.get(ATTR_TARGET_TEMP_STEP)) is None:
            return None
        return TemperatureConverter.convert_interval(
            step, entity.temperature_unit, unit
        )


def _inside(value: float, lowest: float | None, highest: float | None) -> bool:
    """Return whether a setpoint is within the limits that are known."""
    return (lowest is None or value >= lowest) and (highest is None or value <= highest)


def _moved_setpoint(
    target: float, step: float, lowest: float | None, highest: float | None
) -> dict[str, Any] | None:
    """Return the one setpoint a step on, stopping at a limit.

    A setpoint already past a limit, which some integrations report, is left
    where it is. Pulled back inside instead, "warmer" could make it colder,
    or jump it further than the step that was asked for.
    """
    if not _inside(target, lowest, highest):
        return None

    moved = target + step
    if highest is not None:
        moved = min(moved, highest)
    if lowest is not None:
        moved = max(moved, lowest)
    moved = round(moved, _DECIMALS)

    if moved == target:
        return None
    return {ATTR_TEMPERATURE: moved}


def _moved_band(
    low: float,
    high: float,
    step: float,
    lowest: float | None,
    highest: float | None,
) -> dict[str, Any] | None:
    """Return both setpoints a step on, the band between them kept whole.

    One that reaches its limit stops the other too: squeezing the band
    against a limit would leave a thermostat heating and cooling ever closer
    together. A band already past a limit is left where it is.
    """
    if not (_inside(low, lowest, highest) and _inside(high, lowest, highest)):
        return None

    if highest is not None:
        step = min(step, highest - high)
    if lowest is not None:
        step = max(step, lowest - low)
    if not step:
        return None

    return {
        ATTR_TARGET_TEMP_LOW: round(low + step, _DECIMALS),
        ATTR_TARGET_TEMP_HIGH: round(high + step, _DECIMALS),
    }
