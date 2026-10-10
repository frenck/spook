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

from ....const import DOMAIN as SPOOK_DOMAIN
from ....helper_collections import async_get_storage_collection
from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall


class SpookService(AbstractSpookEntityComponentService[Timer]):
    """Home Assistant service to set duration for a timer."""

    domain = DOMAIN
    service = "set_duration"
    # This changes the timer as it is stored, which editing it in the UI only
    # lets an admin do. Starting or pausing it is somebody using it, this is
    # somebody changing it.
    admin_only = True
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
            raise HomeAssistantError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="timer_not_editable",
                translation_placeholders={
                    "entity_id": entity_id,
                },
            )

        # pylint: disable-next=protected-access
        updates = entity._config.copy()  # noqa: SLF001
        item_id = updates.pop(CONF_ID)
        updates.update(
            {
                CONF_DURATION: _format_timedelta(call.data[CONF_DURATION]),
            }
        )

        collection: TimerStorageCollection = async_get_storage_collection(
            entity.hass, DOMAIN
        )

        await collection.async_update_item(item_id, updates)
