"""Spook - Not your homie."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.input_number import DOMAIN, InputNumber
from homeassistant.core import ServiceCall

from . import AbstractSpookEntityComponentService, ReplaceExistingService


class SpookService(AbstractSpookEntityComponentService, ReplaceExistingService):
    """Input number entity service, decrease value by a single step.

    It override the built-in increment service to allow for a custom amount.
    """

    domain = DOMAIN
    service = "decrement"
    schema = {vol.Optional("amount"): vol.Coerce(float)}

    async def async_handle_service(
        self, entity: InputNumber, call: ServiceCall
    ) -> None:
        """Handle the service call."""
        if (amount := call.data.get("amount", entity.step)) % entity.step != 0:
            raise ValueError(
                f"Amount {amount} not valid for {entity.entity_id}, "
                f"it needs to be a multiple of {entity.step}"
            )

        # pylint: disable-next=protected-access
        await entity.set_value(max(entity._current_value + amount, entity._minimum))
