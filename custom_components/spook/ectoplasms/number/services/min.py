"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import DOMAIN, NumberEntity
from homeassistant.exceptions import HomeAssistantError

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[NumberEntity]):
    """Number entity service, set the min value."""

    domain = DOMAIN
    service = "min"

    async def async_handle_service(
        self,
        entity: NumberEntity,
        call: ServiceCall,  # noqa: ARG002
    ) -> None:
        """Handle the service call."""
        if entity.min_value is None:
            msg = f"Entity {entity.entity_id} has no min value"
            raise HomeAssistantError(msg)
        await entity.async_set_native_value(entity.native_min_value)
