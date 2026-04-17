"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.input_number import (
    DOMAIN,
    InputNumber,
    NumberStorageCollection,
)
from homeassistant.exceptions import HomeAssistantError

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[InputNumber]):
    """Input number service to delete a helper on the fly."""

    domain = DOMAIN
    service = "delete"
    schema = {}

    async def async_handle_service(
        self,
        entity: InputNumber,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        if not entity.editable:
            message = f"This input number is not editable: {entity.entity_id}"
            raise HomeAssistantError(message)

        collection: NumberStorageCollection
        if DOMAIN in self.hass.data:
            collection = self.hass.data[DOMAIN]
        else:
            # Major hack to get around edge cases. 👻
            collection = self.hass.data["websocket_api"][
                "input_number/list"
            ][0].__self__.storage_collection
        await collection.async_delete_item(entity.unique_id)
