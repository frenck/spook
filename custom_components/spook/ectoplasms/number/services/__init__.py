"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from homeassistant.components.number import NumberEntity


def native_value_as_float(entity: NumberEntity) -> float:
    """Return the native value of a number entity as a float."""
    try:
        return float(entity.value)
    except (TypeError, ValueError) as err:
        msg = f"Native value {entity.value!r} for {entity.entity_id} is not a number"
        raise HomeAssistantError(msg) from err
