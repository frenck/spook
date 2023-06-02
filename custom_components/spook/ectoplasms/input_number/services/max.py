"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.input_number import DOMAIN, InputNumber

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService):
    """Input number entity service, set the max value."""

    domain = DOMAIN
    service = "max"

    async def async_handle_service(self, entity: InputNumber, _: ServiceCall) -> None:
        """Handle the service call."""
        # pylint: disable-next=protected-access
        await entity.async_set_value(entity._maximum)  # noqa: SLF001
