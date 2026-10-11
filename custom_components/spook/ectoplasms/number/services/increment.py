"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.number import DOMAIN, NumberEntity

from ....services import AbstractSpookEntityComponentService
from . import async_set_shown_value, shown_value_as_float, step_amount

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
        value = shown_value_as_float(entity) + step_amount(entity, call)

        if entity.max_value is not None:
            value = min(value, entity.max_value)

        await async_set_shown_value(entity, value)
