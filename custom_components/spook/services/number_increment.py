"""Spook - Not your homie."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.number import DOMAIN, NumberEntity
from homeassistant.core import ServiceCall

from . import AbstractSpookEntityComponentService


class SpookService(AbstractSpookEntityComponentService):
    """Number entity service, increase value by a single step."""

    domain = DOMAIN
    service = "increment"
    schema = {vol.Optional("amount"): vol.Coerce(float)}

    async def async_handle_service(
        self, entity: NumberEntity, call: ServiceCall
    ) -> None:
        """Handle the service call."""
        if (amount := call.data.get("amount", entity.step or 1)) % entity.step != 0:
            raise ValueError(
                f"Amount {amount} not valid for {entity.entity_id}, "
                f"it needs to be a multiple of {entity.step}"
            )

        value = entity.value + amount

        if entity.max_value is not None:
            value = min(value, entity.max_value)

        await entity.set_native_value(value)
