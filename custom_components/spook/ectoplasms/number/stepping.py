"""Spook - Your homie."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from ...const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.components.number import NumberEntity
    from homeassistant.core import ServiceCall

# Not in `services/__init__.py`: that file is the package namespace, and
# loading the `number.max` and `number.min` actions puts their modules in it,
# right over the built-in `max` and `min` used here. #1944

# Steps are floats, so every comparison against a step boundary needs slack.
_FLOAT_TOLERANCE = 1e-9


def step_amount(entity: NumberEntity, call: ServiceCall) -> float:
    """Return the requested amount, checked against the entity's step.

    Refused with a validation error, the one kind the frontend shows the
    message of when it runs an action. Anything else, a `ValueError` too,
    only reaches it as "Unknown error".
    """
    step = entity.step or 1
    amount = call.data.get("amount", step)
    remainder = amount % step
    # Float modulo wraps around just short of the step, 0.3 % 0.1 is
    # 0.09999999999999998, so a remainder against either end is a clean multiple.
    if not (
        math.isclose(remainder, 0, rel_tol=0, abs_tol=_FLOAT_TOLERANCE)
        or math.isclose(remainder, step, rel_tol=0, abs_tol=_FLOAT_TOLERANCE)
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="amount_not_a_multiple_of_step",
            translation_placeholders={
                "amount": str(amount),
                "entity_id": entity.entity_id,
                "step": str(step),
            },
        )

    return amount


def shown_value_as_float(entity: NumberEntity) -> float:
    """Return the value of a number entity, as it shows it, as a float.

    In the units it shows, which are not always the units it works in: a
    thermostat that keeps Celsius can be shown in Fahrenheit. Stepping from
    this means stepping in what somebody sees, and the result has to go back
    through `async_set_shown_value` to land in the units the entity keeps.
    """
    try:
        return float(entity.value)
    except (TypeError, ValueError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="value_not_a_number",
            translation_placeholders={
                "value": repr(entity.value),
                "entity_id": entity.entity_id,
            },
        ) from err


async def async_set_shown_value(entity: NumberEntity, value: float) -> None:
    """Set a value given in the units the number shows, the way core does.

    Converted to the units the entity works in, and kept within the limits
    it has there. Handing the shown value over as it is set a thermostat
    showing 68 °F to 69 °C on a step of one degree.
    """
    try:
        native_value = entity.convert_to_native_value(value)
        native_value = min(
            max(native_value, entity.native_min_value), entity.native_max_value
        )
        await entity.async_set_native_value(native_value)
    except NotImplementedError:
        await entity.async_set_value(value)
