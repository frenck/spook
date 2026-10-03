"""Tests for the calendar.delete_event action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ServiceNotSupported, ServiceValidationError
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.calendar.services.delete_event import (
    SpookService,
)

from .conftest import AGENDA, READ_ONLY, async_set_up_calendars, event

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


async def _delete(hass: HomeAssistant, **data: Any) -> dict[str, Any]:
    """Delete from the agenda, and return what was handed back for it."""
    response = await hass.services.async_call(
        "calendar",
        "delete_event",
        {"entity_id": AGENDA, **data},
        blocking=True,
        return_response=True,
    )
    return response[AGENDA]


async def test_events_are_found_by_their_title_in_a_window(
    hass: HomeAssistant,
) -> None:
    """Test only events with that title, inside the window, are deleted.

    And each comes back with its uid, which `get_events` never gives.
    """
    agenda = await _setup(hass)
    agenda.events = [
        event("Dentist", 2, "a"),
        event("Dinner", 3, "b"),
        event("Dentist", 48, "c"),
    ]

    result = await _delete(hass, summary="Dentist", duration={"hours": 24})

    assert [found["uid"] for found in result["events"]] == ["a"]
    assert [kept.uid for kept in agenda.events] == ["b", "c"]


async def test_an_event_is_found_by_its_uid(hass: HomeAssistant) -> None:
    """Test a uid alone is enough to say which event."""
    agenda = await _setup(hass)
    agenda.events = [event("Dentist", 2, "a"), event("Dentist", 3, "b")]

    await _delete(hass, uid="b", duration={"hours": 24})

    assert [kept.uid for kept in agenda.events] == ["a"]


async def test_nothing_to_delete_is_not_an_error(hass: HomeAssistant) -> None:
    """Test an empty find hands back nothing, rather than failing.

    "Delete it if it is there" is how an automation tidies up after itself.
    """
    agenda = await _setup(hass)
    agenda.events = [event("Dinner", 3, "b")]

    result = await _delete(hass, summary="Dentist", duration={"hours": 24})

    assert result == {"events": []}
    assert agenda.deleted == []


async def test_an_occurrence_is_deleted_on_its_own(hass: HomeAssistant) -> None:
    """Test an occurrence of a series is deleted, and the rest stays."""
    agenda = await _setup(hass)
    agenda.events = [
        event("Standup", 2, "s", recurrence_id="1"),
        event("Standup", 26, "s", recurrence_id="2"),
    ]

    await _delete(hass, summary="Standup", duration={"hours": 12})

    assert agenda.deleted == [("s", "1")]
    assert [kept.recurrence_id for kept in agenda.events] == ["2"]


async def test_the_whole_series_goes_once(hass: HomeAssistant) -> None:
    """Test asking for the whole series deletes it once, not per occurrence."""
    agenda = await _setup(hass)
    agenda.events = [
        event("Standup", 2, "s", recurrence_id="1"),
        event("Standup", 26, "s", recurrence_id="2"),
    ]

    result = await _delete(
        hass, summary="Standup", duration={"hours": 48}, whole_series=True
    )

    assert agenda.deleted == [("s", None)]
    assert len(result["events"]) == 1
    assert agenda.events == []


async def test_which_events_has_to_be_said(hass: HomeAssistant) -> None:
    """Test a window alone is refused: that empties a calendar by accident."""
    agenda = await _setup(hass)
    agenda.events = [event("Dinner", 3, "b")]

    with pytest.raises(ServiceValidationError):
        await _delete(hass, duration={"hours": 24})

    assert agenda.events


async def test_where_to_look_has_to_be_said(hass: HomeAssistant) -> None:
    """Test a title without an end or a duration is refused."""
    await _setup(hass)

    with pytest.raises(ServiceValidationError):
        await _delete(hass, summary="Dentist")


async def test_a_calendar_that_cannot_delete_says_so(hass: HomeAssistant) -> None:
    """Test a read-only calendar refuses, rather than doing nothing quietly."""
    await _setup(hass)

    with pytest.raises(ServiceNotSupported):
        await hass.services.async_call(
            "calendar",
            "delete_event",
            {"entity_id": READ_ONLY, "summary": "Christmas", "duration": {"days": 1}},
            blocking=True,
            return_response=True,
        )


async def test_a_window_that_ends_before_it_starts_is_refused(
    hass: HomeAssistant,
) -> None:
    """Test an end before the start is an error, not an empty find."""
    await _setup(hass)

    with pytest.raises(ServiceValidationError):
        await _delete(
            hass,
            summary="Dentist",
            start_date_time="2026-10-05 12:00:00",
            end_date_time="2026-10-05 10:00:00",
        )


async def test_an_event_without_a_uid_is_left_alone(hass: HomeAssistant) -> None:
    """Test an event the calendar gives no uid is not asked to be deleted.

    Without one there is no telling the calendar which event is meant.
    """
    agenda = await _setup(hass)
    agenda.events = [event("Dentist", 2, None)]  # type: ignore[arg-type]

    result = await _delete(hass, summary="Dentist", duration={"hours": 24})

    assert result == {"events": []}
    assert agenda.deleted == []
