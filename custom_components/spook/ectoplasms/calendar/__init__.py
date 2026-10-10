"""Spook - Your homie. Finding calendar events to change or remove."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components.calendar.const import (
    EVENT_DURATION,
    EVENT_END_DATETIME,
    EVENT_START_DATETIME,
    EVENT_SUMMARY,
    EVENT_UID,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from ...const import DOMAIN

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.components.calendar import CalendarEntity, CalendarEvent
    from homeassistant.core import ServiceCall

# Which events, and where to look for them. Where to look is read the way
# `calendar.get_events` reads it: from a start, which is now unless given,
# until an end or for a duration.
FIND_SCHEMA = {
    vol.Optional(EVENT_SUMMARY): cv.string,
    vol.Optional(EVENT_UID): cv.string,
    vol.Optional(EVENT_START_DATETIME): cv.datetime,
    vol.Exclusive(EVENT_END_DATETIME, "end"): cv.datetime,
    vol.Exclusive(EVENT_DURATION, "end"): vol.All(
        cv.time_period, cv.positive_timedelta
    ),
}


def _window_of(call: ServiceCall) -> tuple[datetime, datetime]:
    """Return the stretch of time to look in.

    There is no looking through a calendar without saying how far.
    """
    start: datetime = call.data.get(EVENT_START_DATETIME) or dt_util.now()

    if (duration := call.data.get(EVENT_DURATION)) is not None:
        end = start + duration
    elif (end_at := call.data.get(EVENT_END_DATETIME)) is not None:
        end = end_at
    else:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="calendar_range_required",
        )

    if end <= start:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="calendar_range_backwards",
        )

    return dt_util.as_local(start), dt_util.as_local(end)


async def async_find_events(
    entity: CalendarEntity, call: ServiceCall
) -> list[CalendarEvent]:
    """Return the events a call is about, by their title, their uid, or both.

    `calendar.get_events` leaves the uid out of what it returns, so an
    automation that wants to change an event has no way to learn it. Looking
    events up by their title, inside a stretch of time, is what it can do.

    A title or a uid is required. "Everything in the next week" is not a
    question this answers: that is how a calendar gets emptied by accident.
    """
    summary: str | None = call.data.get(EVENT_SUMMARY)
    uid: str | None = call.data.get(EVENT_UID)
    if summary is None and uid is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="calendar_events_which",
        )

    start, end = _window_of(call)
    events = await entity.async_get_events(entity.hass, start, end)

    return [
        event
        for event in events
        if (summary is None or event.summary == summary)
        and (uid is None or event.uid == uid)
    ]


def describe(event: CalendarEvent) -> dict[str, Any]:
    """Return an event the way an action hands it back, uid included."""
    return {
        "uid": event.uid,
        "recurrence_id": event.recurrence_id,
        "summary": event.summary,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
    }
