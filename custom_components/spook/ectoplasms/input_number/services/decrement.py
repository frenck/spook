"""Spook - Your homie."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.input_number import DOMAIN, InputNumber

from ....services import AbstractSpookEntityComponentService, ReplaceExistingService

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
        # pylint: disable=protected-access
        amount = call.data.get("amount", entity._step)  # noqa: SLF001
        if not math.isclose(amount % entity._step, 0, abs_tol=1e-9):  # noqa: SLF001
            msg = (
                f"Amount {amount} not valid for {entity.entity_id}, "
                f"it needs to be a multiple of {entity._step}",  # noqa: SLF001
            )
            raise ValueError(msg)

        await entity.async_set_value(
            max(
                entity._current_value - amount,  # noqa: SLF001
                entity._minimum,  # noqa: SLF001
            ),
        )
