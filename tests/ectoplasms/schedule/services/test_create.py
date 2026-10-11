"""Tests for the schedule.create service.

The shared base is tested in depth with the timer. These pin what is the
schedule's own: a week of time blocks, the checks core runs on them, and that
the base is wired to its domain.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytest
import voluptuous as vol

from homeassistant.components.schedule import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook.ectoplasms.schedule.services import create
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

    from tests.common import MockUser


pytestmark = pytest.mark.usefixtures("spook_translations")

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@pytest.fixture(autouse=True)
async def _schedules(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> AsyncGenerator[None]:
    """Set up one schedule from the UI and one from YAML, and the action."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "minor_version": 1,
        "data": {
            "items": [
                {
                    "id": "heating",
                    "name": "Heating",
                    **{day: [] for day in _DAYS},
                }
            ]
        },
    }
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {"from_yaml": {"name": "From YAML"}}},
    )
    await hass.async_block_till_done()
    create.SpookService(hass).async_register()

    yield

    # A schedule with time blocks keeps a timer for its next change, and
    # stopping Home Assistant does not cancel it. Deleting what the test made
    # does, so nothing outlives the test.
    collection = async_get_storage_collection(hass, DOMAIN)
    for item_id in list(collection.data):
        await collection.async_delete_item(item_id)


async def _stored_week(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    """Return the week a schedule runs on, the way core hands it out."""
    response = await hass.services.async_call(
        DOMAIN,
        "get_schedule",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
        return_response=True,
    )
    return response[entity_id]  # type: ignore[index, return-value]


async def test_create_follows_the_name(hass: HomeAssistant) -> None:
    """Without an ID asked for, the entity ID follows the name, like the UI.

    Days left out are off all day.
    """
    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {"name": "Garden lights"},
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "schedule.garden_lights"}
    assert hass.states.get("schedule.garden_lights") is not None
    assert await _stored_week(hass, "schedule.garden_lights") == {
        day: [] for day in _DAYS
    }


async def test_create_takes_the_entity_id_and_every_day(
    hass: HomeAssistant,
) -> None:
    """The ID asked for wins over the name, and every day lands as stored.

    Blocks come back in order, a block ending at midnight is kept as such,
    and the data on a block stays with it.
    """
    week: dict[str, Any] = {
        day: [{"from": f"0{index}:00", "to": f"0{index}:30"}]
        for index, day in enumerate(_DAYS, start=1)
    }
    week["monday"] = [
        {"from": "17:00", "to": "24:00"},
        {"from": "06:30", "to": "08:30", "data": {"temperature": 21}},
    ]

    response = await hass.services.async_call(
        DOMAIN,
        "create",
        {
            "name": "Living room",
            "schedule_id": "heating_living_room",
            "icon": "mdi:radiator",
            **week,
        },
        blocking=True,
        return_response=True,
    )

    assert response == {ATTR_ENTITY_ID: "schedule.heating_living_room"}
    state = hass.states.get("schedule.heating_living_room")
    assert state is not None
    assert state.attributes["icon"] == "mdi:radiator"

    item = next(
        item
        for item in async_get_storage_collection(hass, DOMAIN).data.values()
        if item["name"] == "Living room"
    )
    assert item["monday"] == [
        {"from": "06:30:00", "to": "08:30:00", "data": {"temperature": 21}},
        {"from": "17:00:00", "to": "24:00:00"},
    ]
    for index, day in enumerate(_DAYS[1:], start=2):
        assert item[day] == [{"from": f"0{index}:00:00", "to": f"0{index}:30:00"}]


async def test_a_created_schedule_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Inside a block, the new schedule is on and shows that block's data."""
    monday_morning = datetime(
        2026, 10, 12, 7, 0, tzinfo=dt_util.get_default_time_zone()
    )
    assert monday_morning.weekday() == 0
    freezer.move_to(monday_morning)

    await hass.services.async_call(
        DOMAIN,
        "create",
        {
            "name": "Wake up",
            "monday": [{"from": "06:30", "to": "08:30", "data": {"scene": "sunrise"}}],
        },
        blocking=True,
    )

    state = hass.states.get("schedule.wake_up")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["scene"] == "sunrise"


@pytest.mark.parametrize(
    ("monday", "message"),
    [
        (
            [{"from": "07:00", "to": "09:00"}, {"from": "08:00", "to": "10:00"}],
            "Overlapping times",
        ),
        ([{"from": "09:00", "to": "07:00"}], "Invalid time range"),
        ([{"from": "09:00", "to": "09:00"}], "Invalid time range"),
        ([{"from": "25:00", "to": "26:00"}], "Invalid time"),
        ([{"from": "07:00"}], "required key not provided"),
        ([{"from": "07:00", "to": "09:00", "data": {"list": [1]}}], "data"),
    ],
)
async def test_create_refuses_a_day_that_does_not_fit(
    hass: HomeAssistant,
    monday: list[dict[str, Any]],
    message: str,
) -> None:
    """Core's own checks on time blocks run before anything is made."""
    with pytest.raises(vol.Invalid, match=message):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Broken", "monday": monday},
            blocking=True,
        )

    assert hass.states.get("schedule.broken") is None
    assert set(async_get_storage_collection(hass, DOMAIN).data) == {"heating"}


async def test_create_refuses_an_entity_id_already_taken(
    hass: HomeAssistant,
) -> None:
    """A taken ID is refused, rather than quietly getting a suffix."""
    with pytest.raises(HomeAssistantError, match=r"schedule\.from_yaml is already"):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Another", "schedule_id": "from_yaml"},
            blocking=True,
        )


async def test_only_an_admin_can_create(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
) -> None:
    """Making a helper is configuration, not everyday use."""
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "create",
            {"name": "Sneaky"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert hass.states.get("schedule.sneaky") is None
