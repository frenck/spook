"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.input_number import DOMAIN, InputNumber

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[InputNumber]):
    """Input number entity service, set the max value."""

    domain = DOMAIN
    service = "max"

    async def async_handle_service(
        self,
        entity: InputNumber,
        call: ServiceCall,  # noqa: ARG002
    ) -> None:
        """Handle the service call."""
        await entity.async_set_native_value(entity.native_max_value)
