"""Spook - Your homie. Reading where a thermostat is, and where it is heading.

Shared by the trigger that fires when a temperature reaches its target and
the condition that asks whether it is there, so the two cannot come to
different answers about the same device.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    HVACMode,
)
from homeassistant.components.water_heater import DOMAIN as WATER_HEATER_DOMAIN
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import split_entity_id

if TYPE_CHECKING:
    from homeassistant.core import State

CONF_TOLERANCE = "tolerance"

DOMAINS = (CLIMATE_DOMAIN, WATER_HEATER_DOMAIN)

# A device that is off, or not there, has a setpoint it is not working
# towards. The temperature drifting onto it is not the device reaching it.
_NOT_WORKING = (STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN)


def validate_tolerance(value: Any) -> float:
    """Validate the tolerance, a distance from the target that still counts."""
    distance = float(vol.Coerce(float)(value))
    if not math.isfinite(distance) or distance < 0:
        message = "The tolerance must be zero or more"
        raise vol.Invalid(message)
    return distance


@dataclass(frozen=True, slots=True)
class Reading:
    """Where a device is, and where it is heading."""

    current: float
    low: float
    high: float

    def at_target(self, tolerance: float) -> bool:
        """Tell whether the temperature is at the target, give or take."""
        return self.low - tolerance <= self.current <= self.high + tolerance

    def same_target(self, other: Reading) -> bool:
        """Tell whether both readings were heading to the same place."""
        return self.low == other.low and self.high == other.high


def _number(value: Any) -> float | None:
    """Return a finite number, or None for anything else."""
    try:
        number = float(value)
    except TypeError, ValueError:
        return None
    return number if math.isfinite(number) else None


def reading(state: State | None) -> Reading | None:
    """Read the current temperature and the target off a state.

    One setpoint is a target of one temperature. A range, as heating and
    cooling to a band does, is reached anywhere inside it.

    A thermostat that can do both reports both, whatever mode it is in. In
    `heat_cool` the band is what it works towards, in any other mode the one
    setpoint is, if it has one.
    """
    if state is None or state.state in _NOT_WORKING:
        return None

    attributes = state.attributes
    if (current := _number(attributes.get(ATTR_CURRENT_TEMPERATURE))) is None:
        return None

    setpoint = _number(attributes.get(ATTR_TEMPERATURE))
    low = _number(attributes.get(ATTR_TARGET_TEMP_LOW))
    high = _number(attributes.get(ATTR_TARGET_TEMP_HIGH))

    if (
        low is not None
        and high is not None
        and (setpoint is None or state.state == HVACMode.HEAT_COOL)
    ):
        return Reading(current, low, high)
    if setpoint is not None:
        return Reading(current, setpoint, setpoint)
    return None


def only_climate_and_water_heaters(entity_ids: set[str]) -> set[str]:
    """Keep what has a target temperature, as an area holds all sorts."""
    return {
        entity_id
        for entity_id in entity_ids
        if split_entity_id(entity_id)[0] in DOMAINS
    }
