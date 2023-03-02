"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components.input_number import DOMAIN, InputNumber

from . import AbstractSpookEntityComponentService, ReplaceExistingService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService, ReplaceExistingService):
    """Input number entity service, increase value by a single step.

    It override the built-in increment service to allow for a custom amount.
    """

    domain = DOMAIN
    service = "increment"
    schema = {vol.Optional("amount"): vol.Coerce(float)}

    async def async_handle_service(
        self,
        entity: InputNumber,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if (amount := call.data.get("amount", entity.step)) % entity.step != 0:
            msg = (
                f"Amount {amount} not valid for {entity.entity_id}, "
                f"it needs to be a multiple of {entity.step}",
            )
            raise ValueError(msg)

        # pylint: disable=protected-access
        await entity.set_value(
            min(
                entity._current_value + amount,  # noqa: SLF001
                entity._maximum,  # noqa: SLF001
            ),
        )
