"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.calendar import (
    DOMAIN,
    CalendarEntity,
    CalendarEntityFeature,
)
from homeassistant.core import SupportsResponse
from homeassistant.helpers import config_validation as cv

from ....services import AbstractSpookEntityComponentService
from .. import FIND_SCHEMA, async_find_events, describe

if TYPE_CHECKING:
    from homeassistant.core import ServiceCall, ServiceResponse

ATTR_WHOLE_SERIES = "whole_series"


class SpookService(AbstractSpookEntityComponentService[CalendarEntity]):
    """Calendar service that deletes events, found by their title or uid.

    Home Assistant can create an event from an automation, and the calendar
    itself can delete one, but only the calendar panel asks it to. An
    automation that puts something in a calendar never gets to take it out
    again.

    Nothing found is not an error. "Delete it if it is there" is what an
    automation tidying up after itself means, and failing on an empty
    calendar would make it stop halfway.
    """

    domain = DOMAIN
    service = "delete_event"
    required_features = [CalendarEntityFeature.DELETE_EVENT]
    supports_response = SupportsResponse.OPTIONAL
    schema = {
        **FIND_SCHEMA,
        vol.Optional(ATTR_WHOLE_SERIES, default=False): cv.boolean,
    }

    async def async_handle_service(
        self,
        entity: CalendarEntity,
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the service call."""
        whole_series: bool = call.data[ATTR_WHOLE_SERIES]
        deleted = []
        series_done: set[str] = set()

        for event in await async_find_events(entity, call):
            # An event the calendar gives no uid cannot be told apart from
            # any other, so there is nothing to ask the calendar to delete.
            if event.uid is None:
                continue

            if event.recurrence_id is None or whole_series:
                # One occurrence of a series found this way stands for all of
                # them, and the next one found is already gone with it.
                if event.uid in series_done:
                    continue
                series_done.add(event.uid)
                await entity.async_delete_event(event.uid)

                # Handed back as the series it was, not as the occurrence
                # that happened to lead to it.
                deleted.append({**describe(event), "recurrence_id": None})
                continue

            await entity.async_delete_event(
                event.uid, recurrence_id=event.recurrence_id
            )
            deleted.append(describe(event))

        return {"events": deleted}
