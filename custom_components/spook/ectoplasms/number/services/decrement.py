"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.number import DOMAIN, NumberEntity

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService):
    """Number entity service, decrease value by a single step."""

    domain = DOMAIN
    service = "decrement"
    schema = {vol.Optional("amount"): vol.Coerce(float)}

    async def async_handle_service(
        self,
        entity: NumberEntity,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if (amount := call.data.get("amount", entity.step or 1)) % entity.step != 0:
            msg = (
                f"Amount {amount} not valid for {entity.entity_id}, "
                f"it needs to be a multiple of {entity.step}",
            )
            raise ValueError(msg)

        value = entity.value - amount

        if entity.min_value is not None:
            value = max(value, entity.min_value)

        await entity.async_set_native_value(value)
