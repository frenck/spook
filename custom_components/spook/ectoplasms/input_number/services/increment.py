"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.input_number import DOMAIN, InputNumber

from ....services import AbstractSpookEntityComponentService, ReplaceExistingService
from . import (
    CONF_CYCLE,
    STEP_SERVICE_SCHEMA,
    cycled_value,
    native_value_as_float,
    step_amount,
)

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(
    AbstractSpookEntityComponentService[InputNumber], ReplaceExistingService
):
    """Input number entity service, increase value by a single step.

    It overrides the built-in increment service to allow for a custom amount,
    and to cycle around the range instead of stopping at the end of it.
    """

    domain = DOMAIN
    service = "increment"
    schema = STEP_SERVICE_SCHEMA

    async def async_handle_service(
        self,
        entity: InputNumber,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        new_value = native_value_as_float(entity) + step_amount(entity, call)

        if new_value > entity.native_max_value:
            new_value = (
                cycled_value(entity, new_value)
                if call.data[CONF_CYCLE]
                else entity.native_max_value
            )

        await entity.async_set_native_value(new_value)
