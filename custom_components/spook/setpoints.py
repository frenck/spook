"""Spook - Your homie. Stepping a setpoint up or down, within its limits.

Shared by the actions that turn something a step warmer, colder, wetter or
drier: a thermostat, a water heater, a humidifier. Home Assistant only knows
setting a value, so each would otherwise read it, add to it, and send it
back, and get the limits wrong in its own way.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_conversion import TemperatureConverter

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

CONF_STEP = "step"

STEP_SCHEMA = {
    vol.Optional(CONF_STEP): vol.All(
        vol.Coerce(float), vol.Range(min=0, min_included=False)
    ),
}

# What the Home Assistant interface steps by when a device does not say.
_DEFAULT_TEMPERATURE_STEP = {
    UnitOfTemperature.CELSIUS: 0.5,
    UnitOfTemperature.FAHRENHEIT: 1.0,
}

# Steps like 0.1 add up to 20.600000000000001 in floats, which no device
# wants to be sent. Two decimals is finer than any of them goes.
_DECIMALS = 2


_LEAST_PERCENT = 1
_MOST_PERCENT = 100


def whole_percent(value: Any) -> int:
    """Validate a step in whole percents, and refuse a fraction or a guess.

    For a position or a humidity, which a device takes in whole percents.
    Cutting 5.9 down to 5 quietly would be a different step than was asked
    for; "5" and 5.0 are still 5. The same care as the quota condition's
    limit: nothing rounds its way through a float.
    """
    return _whole_percent(value, what="step", least=_LEAST_PERCENT)


def whole_position(value: Any) -> int:
    """Validate a position in whole percents, from closed to open.

    The same care as a step, where zero is a place to be rather than no step
    at all.
    """
    return _whole_percent(value, what="position", least=0)


def _whole_percent(value: Any, *, what: str, least: int) -> int:
    """Validate a whole percentage from least to a hundred."""
    # Decimal rather than float, and from the text rather than the value.
    # `float("5.0000000000000001")` is exactly 5.0, so a fraction would round
    # its way through, and a large enough integer raises OverflowError on the
    # way in rather than being refused for being too large. The text also
    # turns `True` away, which as an int would have been a step of one.
    #
    # Even the text can fail: Python refuses to write out an integer of more
    # than a few thousand digits, so it is made in here, and the message
    # only quotes the value once the value could be written out at all.
    try:
        text = str(value)
        as_decimal = Decimal(text)
    except (ArithmeticError, TypeError, ValueError) as err:
        message = f"The {what} must be a whole percentage"
        raise vol.Invalid(message) from err

    message = f"The {what} must be a whole percentage, got '{text}'"

    # Infinity and not-a-number are both "integral" as far as Decimal is
    # concerned, and only fall over on the way to an int.
    if not as_decimal.is_finite() or as_decimal != as_decimal.to_integral_value():
        raise vol.Invalid(message)

    # Checked while still a Decimal: "1e1000000000" is a few characters of
    # config and a billion digits of integer, and building that only to find
    # it too large is the whole cost.
    if not least <= as_decimal <= _MOST_PERCENT:
        message = f"The {what} must be between {least} and {_MOST_PERCENT} percent"
        raise vol.Invalid(message)

    return int(as_decimal)


def temperature_step(
    hass: HomeAssistant,
    call: ServiceCall,
    own_step: float | None,
    unit: str,
) -> float:
    """Return the step to take, in the device's own unit.

    A step given in the call is in Home Assistant's unit, and is turned into
    the device's. Otherwise the device's own step, which already is, or what
    the Home Assistant interface falls back to.
    """
    if (step := call.data.get(CONF_STEP)) is not None:
        return TemperatureConverter.convert_interval(
            step, hass.config.units.temperature_unit, unit
        )
    return own_step or _DEFAULT_TEMPERATURE_STEP.get(
        unit, _DEFAULT_TEMPERATURE_STEP[UnitOfTemperature.CELSIUS]
    )


def inside(value: float, lowest: float | None, highest: float | None) -> bool:
    """Return whether a setpoint is within the limits that are known."""
    return (lowest is None or value >= lowest) and (highest is None or value <= highest)


def moved_setpoint(
    value: float,
    step: float,
    lowest: float | None,
    highest: float | None,
    decimals: int = _DECIMALS,
) -> float | None:
    """Return a setpoint a step on, stopping at a limit, or None for no move.

    Rounded to `decimals`, which is about float noise and nothing else: two
    is finer than any temperature goes, but a volume from 0 to 1 needs more
    to keep a step of 5 percent from 0.456 at 0.506.

    A setpoint already past a limit, which some integrations report, is left
    where it is. Pulled back inside instead, "warmer" could make it colder,
    or jump it further than the step that was asked for.
    """
    if not inside(value, lowest, highest):
        return None

    moved = value + step
    if highest is not None:
        moved = min(moved, highest)
    if lowest is not None:
        moved = max(moved, lowest)
    moved = round(moved, decimals)

    return None if moved == value else moved


def moved_band(
    low: float,
    high: float,
    step: float,
    lowest: float | None,
    highest: float | None,
) -> tuple[float, float] | None:
    """Return both ends of a band a step on, the band kept whole.

    One that reaches its limit stops the other too: squeezing the band
    against a limit would leave a thermostat heating and cooling ever closer
    together. A band already past a limit is left where it is.
    """
    if not (inside(low, lowest, highest) and inside(high, lowest, highest)):
        return None

    if highest is not None:
        step = min(step, highest - high)
    if lowest is not None:
        step = max(step, lowest - low)
    if not step:
        return None

    return round(low + step, _DECIMALS), round(high + step, _DECIMALS)
