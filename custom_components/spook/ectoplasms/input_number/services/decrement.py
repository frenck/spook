"""Spook - Your homie."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.input_number import DOMAIN, InputNumber

from ....services import AbstractSpookEntityComponentService, ReplaceExistingService
from . import native_value_as_float

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(
    AbstractSpookEntityComponentService[InputNumber], ReplaceExistingService
):
    """Input number entity service, decrease value by a single step.

    It override the built-in increment service to allow for a custom amount.
    """

    domain = DOMAIN
    service = "decrement"
    schema = {vol.Optional("amount"): vol.Coerce(float)}

    async def async_handle_service(
        self,
        entity: InputNumber,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        step = entity.native_step
        amount = call.data.get("amount", step)
        remainder = amount % step
        # Float modulo wraps around just short of the step, 0.3 % 0.1 is
        # 0.09999999999999998, so a remainder against either end is a clean multiple.
        if not (
            math.isclose(remainder, 0, abs_tol=1e-9)
            or math.isclose(remainder, step, abs_tol=1e-9)
        ):
            msg = (
                f"Amount {amount} not valid for {entity.entity_id}, "
                f"it needs to be a multiple of {step}"
            )
            raise ValueError(msg)

        await entity.async_set_native_value(
            max(
                native_value_as_float(entity) - amount,
                entity.native_min_value,
            ),
        )
