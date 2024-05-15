"""Spook - Your homie."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.number import DOMAIN, NumberEntity

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[NumberEntity]):
    """Number entity service, increase value by a single step."""

    domain = DOMAIN
    service = "increment"
    schema = {vol.Optional("amount"): vol.Coerce(float)}

    async def async_handle_service(
        self,
        entity: NumberEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        amount = call.data.get("amount", entity.step or 1)
        if not math.isclose(amount % entity.step, 0, abs_tol=1e-9):
            msg = (
                f"Amount {amount} not valid for {entity.entity_id}, "
                f"it needs to be a multiple of {entity.step}",
            )
            raise ValueError(msg)

        value = entity.value + amount

        if entity.max_value is not None:
            value = min(value, entity.max_value)

        await entity.async_set_native_value(value)
