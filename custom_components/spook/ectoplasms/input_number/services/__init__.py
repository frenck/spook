"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from homeassistant.components.input_number import InputNumber


def native_value_as_float(entity: InputNumber) -> float:
    """Return the current value of an input number as a float."""
    try:
        return float(entity.native_value)
    except (TypeError, ValueError) as err:
        msg = f"Value {entity.native_value!r} for {entity.entity_id} is not a number"
        raise HomeAssistantError(msg) from err
