"""Spook - Not your homie."""
from __future__ import annotations

from homeassistant.components.number import DOMAIN, NumberEntity
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError

from . import AbstractSpookEntityComponentService


class SpookService(AbstractSpookEntityComponentService):
    """Number entity service, set the max value."""

    domain = DOMAIN
    service = "max"

    async def async_handle_service(self, entity: NumberEntity, _: ServiceCall) -> None:
        """Handle the service call."""
        if entity.max_value is None:
            raise HomeAssistantError("Entity {self.entity_id} has no max value}")
        await entity.async_set_native_value(entity.native_max_value)
