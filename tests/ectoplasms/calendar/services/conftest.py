"""Calendars to find events in, change and delete."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import (
        AddConfigEntryEntitiesCallback,
    )

AGENDA = "calendar.agenda"
READ_ONLY = "calendar.holidays"


def at(hours: float) -> datetime:
    """Return a moment this many hours from now, on the hour."""
    now = dt_util.now().replace(minute=0, second=0, microsecond=0)
    return now + timedelta(hours=hours)


def an_event(
    summary: str,
    start_hours: float,
    uid: str,
    recurrence_id: str | None = None,
    **details: str,
) -> CalendarEvent:
    """Return an hour-long event starting this many hours from now."""
    return CalendarEvent(
        start=at(start_hours),
        end=at(start_hours + 1),
        summary=summary,
        uid=uid,
        recurrence_id=recurrence_id,
        **details,
    )


def _aware(moment: Any) -> Any:
    """Put the local time zone back on a time, the way a calendar reads it."""
    if isinstance(moment, datetime) and moment.tzinfo is None:
        return moment.replace(tzinfo=dt_util.get_default_time_zone())
    return moment


class FakeCalendar(CalendarEntity):
    """A calendar that keeps its events in a list, and what it was asked."""

    _attr_should_poll = False
    _attr_supported_features = (
        CalendarEntityFeature.DELETE_EVENT | CalendarEntityFeature.UPDATE_EVENT
    )

    def __init__(self, name: str) -> None:
        """Initialize the calendar."""
        self._attr_name = name
        self._attr_unique_id = name
        self.events: list[CalendarEvent] = []
        self.deleted: list[tuple[str, str | None]] = []
        self.updated: list[tuple[str, str | None, dict[str, Any]]] = []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next event."""
        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return the events overlapping a stretch of time."""
        del hass
        return [
            event
            for event in self.events
            if event.start_datetime_local < end_date
            and event.end_datetime_local > start_date
        ]

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Delete one occurrence, or the whole event when none is named."""
        del recurrence_range
        self.deleted.append((uid, recurrence_id))
        self.events = [
            event
            for event in self.events
            if event.uid != uid
            or (recurrence_id is not None and event.recurrence_id != recurrence_id)
        ]

    async def async_update_event(
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Replace an event, or one occurrence of it, with what was given."""
        del recurrence_range
        self.updated.append((uid, recurrence_id, dict(event)))

        # What Local Calendar does to what it is handed: the time zones go,
        # in place, in the caller's own dictionary.
        for key in ("dtstart", "dtend"):
            if isinstance(event[key], datetime):
                event[key] = dt_util.as_local(event[key]).replace(tzinfo=None)
        event = {
            **event,
            "dtstart": _aware(event["dtstart"]),
            "dtend": _aware(event["dtend"]),
        }
        self.events = [
            CalendarEvent(
                start=event["dtstart"],
                end=event["dtend"],
                summary=event["summary"],
                description=event.get("description"),
                location=event.get("location"),
                uid=uid,
                recurrence_id=kept.recurrence_id,
            )
            if kept.uid == uid and kept.recurrence_id == recurrence_id
            else kept
            for kept in self.events
        ]


class ReadOnlyCalendar(FakeCalendar):
    """A calendar that can be read and nothing else, like a holiday feed."""

    _attr_supported_features = CalendarEntityFeature(0)


async def async_set_up_calendars(hass: HomeAssistant) -> dict[str, Any]:
    """Set up an agenda that can change, and one that cannot."""
    calendars = {
        AGENDA: FakeCalendar("agenda"),
        READ_ONLY: ReadOnlyCalendar("holidays"),
    }

    async def _setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.CALENDAR])
        return True

    async def _setup_platform(
        _hass: HomeAssistant,
        _entry: ConfigEntry,
        add: AddConfigEntryEntitiesCallback,
    ) -> None:
        add(list(calendars.values()))

    mock_integration(hass, MockModule("fake", async_setup_entry=_setup_entry))
    mock_platform(hass, "fake.config_flow")
    mock_platform(
        hass, "fake.calendar", MockPlatform(async_setup_entry=_setup_platform)
    )

    class _Flow(ConfigFlow, domain="fake"):
        """A config flow that does nothing."""

    with mock_config_flow("fake", _Flow):
        entry = MockConfigEntry(domain="fake")
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return calendars
