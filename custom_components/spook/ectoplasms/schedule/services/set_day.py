"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.schedule import (
    DOMAIN,
    STORAGE_SCHEDULE_SCHEMA,
    WEEKDAY_TO_CONF,
    Schedule,
)
from homeassistant.const import CONF_ID
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ....const import DOMAIN as SPOOK_DOMAIN
from ....helper_collections import async_get_storage_collection
from ....services import AbstractSpookEntityComponentService

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall

CONF_DAY = "day"
CONF_BLOCKS = "blocks"


class SpookService(AbstractSpookEntityComponentService[Schedule]):
    """Schedule service to replace the time blocks of one or more days."""

    domain = DOMAIN
    service = "set_day"
    # This changes the schedule as it is stored, which editing it in the UI
    # only lets an admin do. Reading it is using it, this is changing it.
    admin_only = True
    schema = {
        vol.Required(CONF_DAY): vol.All(
            cv.ensure_list,
            vol.Length(min=1),
            [vol.In(list(WEEKDAY_TO_CONF.values()))],
        ),
        # Only made a list here. What goes in it is for core to judge, below,
        # so a block it refuses comes back as an error people can read.
        vol.Required(CONF_BLOCKS): cv.ensure_list,
    }

    async def async_handle_service(
        self,
        entity: Schedule,
        call: ServiceCall,
    ) -> None:
        """Handle the service call."""
        entity_id = entity.entity_id
        collection = async_get_storage_collection(self.hass, DOMAIN)

        # A schedule from YAML is not in the collection the UI keeps, and
        # changing it there would not survive the next reload anyway.
        if (item_id := entity.unique_id) not in collection.data:
            raise HomeAssistantError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="yaml_schedule_not_editable",
                translation_placeholders={
                    "entity_id": entity_id,
                },
            )

        # Core's own check for a day, the one its helper dialog is held to:
        # times that read as times, blocks that end after they start and do
        # not overlap, and times written the way storage keeps them.
        try:
            days = {
                day: STORAGE_SCHEDULE_SCHEMA[day](call.data[CONF_BLOCKS])
                for day in dict.fromkeys(call.data[CONF_DAY])
            }
        except vol.Invalid as err:
            raise ServiceValidationError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="schedule_blocks_invalid",
                translation_placeholders={
                    "entity_id": entity_id,
                    "error": str(err),
                },
            ) from err

        # Core replaces the whole schedule on an update, so the days not asked
        # for go along as they are. Nothing is awaited between reading them
        # and core storing the result, so this cannot undo a change made by
        # another call in between.
        updates = {
            key: value
            for key, value in collection.data[item_id].items()
            if key != CONF_ID
        }
        updates.update(days)
        await collection.async_update_item(item_id, updates)
