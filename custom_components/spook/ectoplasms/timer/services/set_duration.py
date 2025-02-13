"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.timer import (
    CONF_DURATION,
    DOMAIN,
    Timer,
    TimerStorageCollection,
    _format_timedelta,
)
from homeassistant.const import CONF_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[Timer]):
    """Home Assistant service to set duration for a timer."""

    domain = DOMAIN
    service = "set_duration"
    schema = {
        vol.Required(CONF_DURATION): cv.time_period,
    }

    async def async_handle_service(
        self,
        entity: Timer,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        entity_id = entity.entity_id

        if not entity.editable or not entity.unique_id:
            message = f"This timer is not editable: {entity_id}"
            raise HomeAssistantError(message)

        # pylint: disable-next=protected-access
        updates = entity._config.copy()  # noqa: SLF001
        item_id = updates.pop(CONF_ID)
        updates.update(
            {
                CONF_DURATION: _format_timedelta(call.data[CONF_DURATION]),
            }
        )

        collection: TimerStorageCollection
        if DOMAIN in entity.hass.data:
            collection = entity.hass.data[DOMAIN]
        else:
            # Major hack borrowed from ../../zone/services/create.py:27  👻
            collection = entity.hass.data["websocket_api"]["timer/list"][
                0
            ].__self__.storage_collection

        await collection.async_update_item(item_id, updates)
