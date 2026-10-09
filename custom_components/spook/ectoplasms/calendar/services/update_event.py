"""Spook - Your homie."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.calendar import (
    DOMAIN,
    WEBSOCKET_EVENT_SCHEMA,
    CalendarEntity,
    CalendarEntityFeature,
)
from homeassistant.components.calendar.const import (
    EVENT_DESCRIPTION,
    EVENT_END,
    EVENT_LOCATION,
    EVENT_START,
    EVENT_SUMMARY,
)
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from ....const import DOMAIN as SPOOK_DOMAIN
from ....services import AbstractSpookEntityComponentService
from .. import FIND_SCHEMA, async_find_events, describe

if TYPE_CHECKING:
    from datetime import date, datetime

    from homeassistant.components.calendar import CalendarEvent
    from homeassistant.core import ServiceCall, ServiceResponse

ATTR_NEW_SUMMARY = "new_summary"
ATTR_NEW_START = "new_start"
ATTR_NEW_END = "new_end"
ATTR_SHIFT = "shift"

_CHANGES = (
    ATTR_NEW_SUMMARY,
    EVENT_DESCRIPTION,
    EVENT_LOCATION,
    ATTR_NEW_START,
    ATTR_NEW_END,
    ATTR_SHIFT,
)


def _local(moment: date | datetime) -> date | datetime:
    """Return a time in Home Assistant's own time zone, a date as it is.

    A calendar can keep its events in a zone of its own, and a time written
    in an automation often has none. Home Assistant refuses an event whose
    start and end are in different zones, so both are brought home first. A
    time without a zone is read as local, as everywhere in Home Assistant.
    """
    if not hasattr(moment, "tzinfo"):
        return moment
    if moment.tzinfo is None:
        return moment.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_local(moment)


class SpookService(AbstractSpookEntityComponentService[CalendarEntity]):
    """Calendar service that changes events, found by their title or uid.

    Home Assistant hands the calendar a whole event to update, not the parts
    that change, so what is not asked for is taken from the event as it is.

    An occurrence of a repeating event is changed on its own, never the whole
    series. Changing a series means changing its first event, and the times
    of whichever occurrence happened to be found would move the series start
    along with it.
    """

    domain = DOMAIN
    service = "update_event"
    required_features = [CalendarEntityFeature.UPDATE_EVENT]
    supports_response = SupportsResponse.OPTIONAL
    schema = {
        **FIND_SCHEMA,
        vol.Optional(ATTR_NEW_SUMMARY): cv.string,
        vol.Optional(EVENT_DESCRIPTION): cv.string,
        vol.Optional(EVENT_LOCATION): cv.string,
        vol.Exclusive(ATTR_NEW_START, "move"): cv.datetime,
        vol.Optional(ATTR_NEW_END): cv.datetime,
        vol.Exclusive(ATTR_SHIFT, "move"): cv.time_period,
    }

    async def async_handle_service(
        self,
        entity: CalendarEntity,
        call: ServiceCall,
    ) -> ServiceResponse:
        """Handle the service call."""
        if not any(change in call.data for change in _CHANGES):
            raise ServiceValidationError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="event_nothing_to_change",
            )

        if ATTR_NEW_END in call.data and ATTR_SHIFT in call.data:
            raise ServiceValidationError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="event_shift_or_times",
            )

        updated = []
        for event in await async_find_events(entity, call):
            # An event the calendar gives no uid cannot be told apart from
            # any other, so there is nothing to ask the calendar to change.
            if event.uid is None:
                continue

            changed = self._changed(event, call.data)

            # A copy: Local Calendar strips the time zones off what it is
            # handed, in place, and the response is read from this one.
            await entity.async_update_event(
                event.uid, dict(changed), recurrence_id=event.recurrence_id
            )
            updated.append(
                {
                    **describe(event),
                    "summary": changed[EVENT_SUMMARY],
                    "start": changed[EVENT_START].isoformat(),
                    "end": changed[EVENT_END].isoformat(),
                }
            )

        return {"events": updated}

    @staticmethod
    def _changed(event: CalendarEvent, data: dict[str, Any]) -> dict[str, Any]:
        """Return the event as it is, with what was asked for changed.

        Given only a new start, the event keeps its length. Checked the way
        the calendar panel's own edits are, so an end before its start, or a
        date mixed with a time, is refused here rather than by the calendar.
        """
        start = _local(event.start)
        end = _local(event.end)
        if (shift := data.get(ATTR_SHIFT)) is not None:
            # A day-long event has dates, and a date silently drops any part
            # of a day added to it: an hour later would change nothing, and
            # still be reported as done.
            if not hasattr(start, "tzinfo") and shift % timedelta(days=1):
                raise ServiceValidationError(
                    translation_domain=SPOOK_DOMAIN,
                    translation_key="event_whole_days",
                    translation_placeholders={"summary": str(event.summary)},
                )
            start, end = start + shift, end + shift
        if (new_start := data.get(ATTR_NEW_START)) is not None:
            new_start = _local(new_start)
            end = new_start + (end - start)
            start = new_start
        if (new_end := data.get(ATTR_NEW_END)) is not None:
            end = _local(new_end)

        changed: dict[str, Any] = {
            EVENT_SUMMARY: data.get(ATTR_NEW_SUMMARY, event.summary),
            EVENT_START: start,
            EVENT_END: end,
        }
        for field in (EVENT_DESCRIPTION, EVENT_LOCATION):
            if (value := data.get(field, getattr(event, field))) is not None:
                changed[field] = value

        try:
            return WEBSOCKET_EVENT_SCHEMA(changed)  # type: ignore[no-any-return]
        except vol.Invalid as err:
            raise ServiceValidationError(
                translation_domain=SPOOK_DOMAIN,
                translation_key="event_cannot_change",
                translation_placeholders={
                    "summary": event.summary,
                    "error": err,
                },
            ) from err
