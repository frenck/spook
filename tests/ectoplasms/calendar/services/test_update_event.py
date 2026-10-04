"""Tests for the calendar.update_event action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ServiceNotSupported, ServiceValidationError
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.calendar.services.update_event import (
    SpookService,
)

from .conftest import AGENDA, READ_ONLY, an_event, async_set_up_calendars, at

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .conftest import FakeCalendar


async def _setup(hass: HomeAssistant) -> FakeCalendar:
    """Set up the calendars and the action, and return the agenda."""
    assert await async_setup_component(hass, "homeassistant", {})
    calendars = await async_set_up_calendars(hass)
    SpookService(hass).async_register()
    await hass.async_block_till_done()
    return calendars[AGENDA]


async def _update(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    """Change events on the agenda, and return what was handed back for it."""
    response = await hass.services.async_call(
        "calendar",
        "update_event",
        {"entity_id": AGENDA, "duration": {"hours": 24}, **data},
        blocking=True,
        return_response=True,
    )
    return response[AGENDA]


async def test_a_new_title_keeps_the_rest(hass: HomeAssistant) -> None:
    """Test changing the title leaves the times, place and description.

    The calendar is handed a whole event, so whatever is not changed has to
    be carried over from the event as it is.
    """
    agenda = await _setup(hass)
    agenda.events = [
        an_event("Dentist", 2, "a", location="Main street", description="Bring card"),
        an_event("Dinner", 3, "b"),
    ]

    result = await _update(hass, summary="Dentist", new_summary="Orthodontist")

    changed = agenda.events[0]
    assert changed.summary == "Orthodontist"
    assert (changed.start, changed.end) == (at(2), at(3))
    assert changed.location == "Main street"
    assert changed.description == "Bring card"
    assert agenda.events[1].summary == "Dinner"
    assert result["events"][0]["uid"] == "a"
    assert result["events"][0]["summary"] == "Orthodontist"


async def test_a_shift_moves_the_whole_event(hass: HomeAssistant) -> None:
    """Test a shift moves start and end alike, back as well as forward."""
    agenda = await _setup(hass)
    agenda.events = [an_event("Dentist", 4, "a")]

    await _update(hass, summary="Dentist", shift={"hours": -1})

    assert (agenda.events[0].start, agenda.events[0].end) == (at(3), at(4))


async def test_a_new_start_keeps_the_length(hass: HomeAssistant) -> None:
    """Test moving the start alone takes the end along."""
    agenda = await _setup(hass)
    agenda.events = [an_event("Dentist", 2, "a")]

    await _update(hass, summary="Dentist", new_start=at(5).isoformat())

    assert (agenda.events[0].start, agenda.events[0].end) == (at(5), at(6))


async def test_a_new_end_changes_only_the_end(hass: HomeAssistant) -> None:
    """Test a new end makes the event longer, from where it starts."""
    agenda = await _setup(hass)
    agenda.events = [an_event("Dentist", 2, "a")]

    await _update(hass, summary="Dentist", new_end=at(4).isoformat())

    assert (agenda.events[0].start, agenda.events[0].end) == (at(2), at(4))


async def test_an_occurrence_is_changed_on_its_own(hass: HomeAssistant) -> None:
    """Test an occurrence of a series changes, and the series does not.

    Changing a series means changing its first event, and this occurrence's
    times would move the whole series start along with it.
    """
    agenda = await _setup(hass)
    agenda.events = [
        an_event("Standup", 2, "s", recurrence_id="1"),
        an_event("Standup", 26, "s", recurrence_id="2"),
    ]

    await _update(hass, summary="Standup", new_summary="Retro", duration={"hours": 12})

    assert [(uid, occurrence) for uid, occurrence, _ in agenda.updated] == [("s", "1")]
    assert [kept.summary for kept in agenda.events] == ["Retro", "Standup"]


async def test_something_to_change_has_to_be_said(hass: HomeAssistant) -> None:
    """Test finding events without changing anything is refused."""
    agenda = await _setup(hass)
    agenda.events = [an_event("Dentist", 2, "a")]

    with pytest.raises(ServiceValidationError):
        await _update(hass, summary="Dentist")

    assert agenda.updated == []


async def test_a_shift_and_a_new_end_together_are_refused(
    hass: HomeAssistant,
) -> None:
    """Test moving by a shift and to a new end at once is refused."""
    agenda = await _setup(hass)
    agenda.events = [an_event("Dentist", 2, "a")]

    with pytest.raises(ServiceValidationError):
        await _update(
            hass, summary="Dentist", shift={"hours": 1}, new_end=at(9).isoformat()
        )

    assert agenda.updated == []


async def test_an_end_before_the_start_is_refused(hass: HomeAssistant) -> None:
    """Test an event that would end before it starts never reaches the calendar."""
    agenda = await _setup(hass)
    agenda.events = [an_event("Dentist", 2, "a")]

    with pytest.raises(ServiceValidationError):
        await _update(hass, summary="Dentist", new_end=at(1).isoformat())

    assert agenda.updated == []


async def test_nothing_found_changes_nothing(hass: HomeAssistant) -> None:
    """Test an empty find hands back nothing, rather than failing."""
    agenda = await _setup(hass)
    agenda.events = [an_event("Dinner", 3, "b")]

    result = await _update(hass, summary="Dentist", new_summary="Orthodontist")

    assert result == {"events": []}
    assert agenda.updated == []


async def test_a_calendar_that_cannot_change_says_so(hass: HomeAssistant) -> None:
    """Test a read-only calendar refuses, rather than doing nothing quietly."""
    await _setup(hass)

    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            "calendar",
            "update_event",
            {
                "entity_id": READ_ONLY,
                "summary": "Christmas",
                "duration": {"days": 1},
                "new_summary": "Xmas",
            },
            blocking=True,
            return_response=True,
        )


async def test_an_event_without_a_uid_is_left_alone(hass: HomeAssistant) -> None:
    """Test an event the calendar gives no uid is not asked to be changed."""
    agenda = await _setup(hass)
    agenda.events = [an_event("Dentist", 2, None)]  # type: ignore[arg-type]

    result = await _update(hass, summary="Dentist", new_summary="Orthodontist")

    assert result == {"events": []}
    assert agenda.updated == []


async def test_a_time_without_a_zone_is_read_as_local(hass: HomeAssistant) -> None:
    """Test a new time written plainly, as in YAML, lands where it reads.

    Home Assistant refuses an event whose start and end are in different
    zones, and a plain time has none at all.
    """
    agenda = await _setup(hass)
    agenda.events = [an_event("Dentist", 2, "a")]

    await _update(
        hass, summary="Dentist", new_end=at(4).replace(tzinfo=None).isoformat()
    )

    assert (agenda.events[0].start, agenda.events[0].end) == (at(2), at(4))
