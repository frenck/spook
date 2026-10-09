"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError

from ....const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.components.number import NumberEntity


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
