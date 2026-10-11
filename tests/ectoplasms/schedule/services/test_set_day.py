"""Tests for the schedule.set_day service."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import pytest
import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.components.schedule import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import Context
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.spook.ectoplasms.schedule.services import set_day
from custom_components.spook.helper_collections import async_get_storage_collection

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

    from tests.common import MockUser


pytestmark = pytest.mark.usefixtures("spook_translations")

_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_MORNING = {"from": "07:00:00", "to": "09:00:00"}
_EVENING = {"from": "17:00:00", "to": "22:00:00", "data": {"temperature": 21}}


@pytest.fixture(autouse=True)
async def _schedules(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> AsyncGenerator[None]:
    """Set up one schedule from the UI and one from YAML, and the action.

    The UI one runs every morning, and has an icon, so a change that drops
    something it was not asked to touch shows.
    """
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "minor_version": 1,
        "data": {
            "items": [
                {
                    "id": "heating",
                    "name": "Heating",
                    "icon": "mdi:radiator",
                    **{day: [_MORNING] for day in _DAYS},
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
    set_day.SpookService(hass).async_register()

    yield

    # A schedule with time blocks keeps a timer for its next change, and
    # stopping Home Assistant does not cancel it. Deleting the UI one does,
    # so nothing outlives the test. The YAML one has no blocks to time.
    collection = async_get_storage_collection(hass, DOMAIN)
    for item_id in list(collection.data):
        await collection.async_delete_item(item_id)


def _stored(hass: HomeAssistant) -> dict[str, Any]:
    """Return the UI schedule the way storage keeps it."""
    return dict(async_get_storage_collection(hass, DOMAIN).data["heating"])


async def _set_day(
    hass: HomeAssistant,
    data: dict[str, Any],
    *,
    entity_id: str = "schedule.heating",
    context: Context | None = None,
) -> None:
    """Call the action on a schedule."""
    await hass.services.async_call(
        DOMAIN,
        "set_day",
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
        context=context,
    )
    await hass.async_block_till_done()


async def test_set_one_day(hass: HomeAssistant) -> None:
    """The day asked for gets the new blocks, the rest stays as it was.

    Blocks are stored in order, the way core writes times, with a block
    ending at midnight and the data on a block kept as given.
    """
    await _set_day(
        hass,
        {
            "day": "saturday",
            "blocks": [
                {"from": "17:00", "to": "24:00", "data": {"temperature": 21}},
                {"from": "08:00", "to": "12:00"},
            ],
        },
    )

    stored = _stored(hass)
    assert stored["saturday"] == [
        {"from": "08:00:00", "to": "12:00:00"},
        {"from": "17:00:00", "to": "24:00:00", "data": {"temperature": 21}},
    ]
    for day in _DAYS:
        if day != "saturday":
            assert stored[day] == [_MORNING]
    assert stored["name"] == "Heating"
    assert stored["icon"] == "mdi:radiator"

    response = await hass.services.async_call(
        DOMAIN,
        "get_schedule",
        {ATTR_ENTITY_ID: "schedule.heating"},
        blocking=True,
        return_response=True,
    )
    assert len(response["schedule.heating"]["saturday"]) == len(stored["saturday"])  # type: ignore[index, arg-type]


async def test_set_several_days_at_once(hass: HomeAssistant) -> None:
    """A list of days all get the same blocks, a day twice is one day."""
    await _set_day(
        hass,
        {"day": ["saturday", "sunday", "saturday"], "blocks": [_EVENING]},
    )

    stored = _stored(hass)
    assert stored["saturday"] == [_EVENING]
    assert stored["sunday"] == [_EVENING]
    assert stored["friday"] == [_MORNING]


async def test_an_empty_list_clears_the_day(hass: HomeAssistant) -> None:
    """No blocks leaves the day off all day."""
    await _set_day(hass, {"day": "monday", "blocks": []})

    assert _stored(hass)["monday"] == []
    assert _stored(hass)["tuesday"] == [_MORNING]


async def test_the_schedule_follows_the_new_blocks(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The running schedule picks up the change straight away."""
    monday_noon = datetime(2026, 10, 12, 12, 0, tzinfo=dt_util.get_default_time_zone())
    assert monday_noon.weekday() == 0
    freezer.move_to(monday_noon)
    await _set_day(hass, {"day": "monday", "blocks": [_MORNING]})
    assert hass.states.get("schedule.heating").state == STATE_OFF

    await _set_day(
        hass,
        {
            "day": "monday",
            "blocks": [{"from": "11:00", "to": "13:00", "data": {"mode": "lunch"}}],
        },
    )

    state = hass.states.get("schedule.heating")
    assert state.state == STATE_ON
    assert state.attributes["mode"] == "lunch"


@pytest.mark.parametrize(
    ("blocks", "message"),
    [
        (
            [{"from": "07:00", "to": "09:00"}, {"from": "08:00", "to": "10:00"}],
            "Overlapping times found in schedule",
        ),
        ([{"from": "09:00", "to": "07:00"}], "Invalid time range"),
        ([{"from": "09:00", "to": "09:00"}], "Invalid time range"),
        ([{"from": "25:00", "to": "26:00"}], "Invalid time specified: 25:00"),
        ([{"from": "07:00"}], "required key not provided"),
        ([{"from": "07:00", "to": "09:00", "data": {"list": [1]}}], "data"),
        ([{"from": "07:00", "to": "09:00", "until": "10:00"}], "until"),
        (["07:00-09:00"], "expected a mapping"),
    ],
)
async def test_blocks_core_refuses(
    hass: HomeAssistant,
    blocks: list[Any],
    message: str,
) -> None:
    """Core's own checks run, its reason comes back, and nothing changes."""
    with pytest.raises(ServiceValidationError, match=message) as err:
        await _set_day(hass, {"day": ["monday", "tuesday"], "blocks": blocks})

    assert err.value.translation_key == "schedule_blocks_invalid"
    assert str(err.value).startswith(
        "Those time blocks do not work for schedule.heating: "
    )
    assert str(err.value).endswith("Nothing has been changed")
    assert _stored(hass)["monday"] == [_MORNING]
    assert _stored(hass)["tuesday"] == [_MORNING]


@pytest.mark.parametrize(
    "day",
    ["someday", "mon", [], ["monday", "funday"]],
)
async def test_a_day_that_does_not_exist(hass: HomeAssistant, day: Any) -> None:
    """Only the seven days core keeps can be set."""
    with pytest.raises(vol.Invalid):
        await _set_day(hass, {"day": day, "blocks": [_EVENING]})

    assert _stored(hass)["monday"] == [_MORNING]


@pytest.mark.parametrize(
    "data",
    [
        {"day": "monday"},
        {"day": "monday", "blocks": None},
    ],
)
async def test_the_blocks_have_to_be_given(
    hass: HomeAssistant,
    data: dict[str, Any],
) -> None:
    """Clearing a day is asked for with an empty list, never by leaving out."""
    with pytest.raises(vol.Invalid):
        await _set_day(hass, data)

    assert _stored(hass)["monday"] == [_MORNING]


async def test_a_yaml_schedule_is_refused(hass: HomeAssistant) -> None:
    """A schedule from YAML can only be changed in the YAML."""
    with pytest.raises(HomeAssistantError) as err:
        await _set_day(
            hass,
            {"day": "monday", "blocks": [_EVENING]},
            entity_id="schedule.from_yaml",
        )

    assert err.value.translation_key == "yaml_schedule_not_editable"
    assert str(err.value) == (
        "schedule.from_yaml is a schedule from your YAML configuration, which "
        "Spook cannot change. Edit it in your configuration instead"
    )
    response = await hass.services.async_call(
        DOMAIN,
        "get_schedule",
        {ATTR_ENTITY_ID: "schedule.from_yaml"},
        blocking=True,
        return_response=True,
    )
    assert response["schedule.from_yaml"]["monday"] == []  # type: ignore[index]


async def test_an_unknown_schedule_changes_nothing(hass: HomeAssistant) -> None:
    """Home Assistant finds no schedule to call it on, so nothing changes."""
    await _set_day(
        hass,
        {"day": "monday", "blocks": [_EVENING]},
        entity_id="schedule.nope",
    )

    assert set(async_get_storage_collection(hass, DOMAIN).data) == {"heating"}
    assert _stored(hass)["monday"] == [_MORNING]


async def test_an_admin_can_change_it(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
) -> None:
    """An admin is who the schedule dialog is for."""
    await _set_day(
        hass,
        {"day": "monday", "blocks": [_EVENING]},
        context=Context(user_id=hass_admin_user.id),
    )

    assert _stored(hass)["monday"] == [_EVENING]


async def test_somebody_who_is_not_an_admin_cannot(
    hass: HomeAssistant,
    hass_owner_user: MockUser,
) -> None:
    """Changing a schedule as it is stored is configuration, not using it.

    The user here may use every entity, so the refusal is the admin check,
    not the entity being out of reach.
    """
    # Somebody else owns the house, or the first user made becomes its owner.
    assert hass_owner_user.is_owner
    user = await hass.auth.async_create_user(
        "Allowed to use it", group_ids=[GROUP_ID_USER]
    )
    assert not user.is_admin

    with pytest.raises(Unauthorized):
        await _set_day(
            hass,
            {"day": "monday", "blocks": [_EVENING]},
            context=Context(user_id=user.id),
        )

    assert _stored(hass)["monday"] == [_MORNING]
