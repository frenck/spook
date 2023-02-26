"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components.input_number import DOMAIN, InputNumber
from homeassistant.core import ServiceCall

from . import AbstractSpookEntityComponentService


class SpookService(AbstractSpookEntityComponentService):
    """Input number entity service, set the min value."""

    domain = DOMAIN
    service = "min"

    async def async_handle_service(self, entity: InputNumber, _: ServiceCall) -> None:
        """Handle the service call."""
        # pylint: disable-next=protected-access
        await entity.set_value(entity._minimum)
