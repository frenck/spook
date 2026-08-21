"""Spook - Your homie."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

if TYPE_CHECKING:
    from homeassistant.components.input_number import InputNumber
    from homeassistant.core import ServiceCall

CONF_AMOUNT = "amount"
CONF_CYCLE = "cycle"

# Steps are floats, so every comparison against a step boundary needs slack.
_FLOAT_TOLERANCE = 1e-9

STEP_SERVICE_SCHEMA = {
    vol.Optional(CONF_AMOUNT): vol.Coerce(float),
    vol.Optional(CONF_CYCLE, default=False): cv.boolean,
}


def native_value_as_float(entity: InputNumber) -> float:
    """Return the current value of an input number as a float."""
    try:
        return float(entity.native_value)
    except (TypeError, ValueError) as err:
        msg = f"Value {entity.native_value!r} for {entity.entity_id} is not a number"
        raise HomeAssistantError(msg) from err


def step_amount(entity: InputNumber, call: ServiceCall) -> float:
    """Return the requested amount, checked against the entity's step."""
    step = entity.native_step
    amount = call.data.get(CONF_AMOUNT, step)
    remainder = amount % step
    # Float modulo wraps around just short of the step, 0.3 % 0.1 is
    # 0.09999999999999998, so a remainder against either end is a clean multiple.
    if not (
        math.isclose(remainder, 0, rel_tol=0, abs_tol=_FLOAT_TOLERANCE)
        or math.isclose(remainder, step, rel_tol=0, abs_tol=_FLOAT_TOLERANCE)
    ):
        msg = (
            f"Amount {amount} not valid for {entity.entity_id}, "
            f"it needs to be a multiple of {step}"
        )
        raise ValueError(msg)

    return amount


def cycled_value(entity: InputNumber, value: float) -> float:
    """Wrap a value around the entity's range.

    Home Assistant cycles a select by taking the new index modulo the number
    of options. The same thing here means the positions on the step grid from
    the minimum to the maximum, so overshooting one end carries on from the
    other rather than landing on it. Stepping one past the maximum reaches the
    minimum, and stepping five past it reaches the fifth value up.
    """
    minimum = entity.native_min_value
    step = entity.native_step

    # Floored, because the step does not have to divide the range. Rounding
    # would invent a slot above the maximum: a step of 0.6 across 0 to 1 would
    # offer 1.2, and setting that raises. The tolerance keeps a quotient that
    # is a whole number in spirit, like 10 steps of 0.1, from flooring down.
    quotient = (entity.native_max_value - minimum) / step
    slots = math.floor(quotient + _FLOAT_TOLERANCE) + 1

    # Counted in whole steps, so float drift cannot push the result into the
    # neighbouring slot on the way through the modulo.
    offset = round((value - minimum) / step)

    return minimum + (offset % slots) * step
