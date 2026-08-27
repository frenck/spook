"""Tests for the spook.cron trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.cron import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

CRON_MODULE = "custom_components.spook.ectoplasms.spook.triggers.cron"
# `weekday()` counts Monday as 0; crontab counts it as 1.
MONDAY = 0
FIFTEENTH = 15
MORNING_SEVEN = 7


async def _detach(hass: HomeAssistant) -> None:
    """Turn the automation off, which detaches its trigger.

    Home Assistant's test harness fails a test that leaves a timer behind, so
    this doubles as a check that the trigger cleans up after itself.
    """
    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.on_a_schedule"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def _automation(hass: HomeAssistant, schedule: str) -> list[str]:
    """Set up an automation on a cron schedule and report each time it runs."""
    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["at"])

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "on a schedule",
                    "trigger": {
                        "platform": "spook.cron",
                        "options": {"schedule": schedule},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {"at": "{{ trigger.now }}"},
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key.

    Plain, because Home Assistant prefixes it with the providing integration
    itself: this is `spook.cron` by the time anybody writes it in YAML.
    """
    assert "cron" in await async_get_triggers(hass)


async def test_a_nonsense_expression_is_refused(hass: HomeAssistant) -> None:
    """A bad expression is rejected at validation, naming what is wrong.

    Better here than at three in the morning when the automation was supposed
    to run.
    """
    with pytest.raises(vol.Invalid, match="Invalid crontab expression"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": "not a schedule"}}
        )


async def test_nicknames_are_refused(hass: HomeAssistant) -> None:
    """`@daily` and friends are not crontab as cronsim reads it.

    Worth pinning: it is the first thing somebody used to cron will try, and
    the documentation says so because of this.
    """
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": "@daily"}}
        )


@pytest.mark.parametrize("schedule", ["*/15 * * * * *", "* * * * * *", "0 7 * * *  *"])
async def test_a_seconds_field_is_refused(hass: HomeAssistant, schedule: str) -> None:
    """Cronsim's six-field form is not offered.

    Its leading field is seconds, so `* * * * * *` would run an automation
    every second. Five fields is what this documents, and what it takes.
    """
    with pytest.raises(vol.Invalid, match="expected 5 fields"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": schedule}}
        )


async def test_an_empty_schedule_is_refused(hass: HomeAssistant) -> None:
    """An empty expression is caught by the field count, not by cronsim."""
    with pytest.raises(vol.Invalid, match="expected 5 fields"):
        await SpookTrigger.async_validate_config(hass, {"options": {"schedule": "   "}})


async def test_a_valid_expression_is_accepted(hass: HomeAssistant) -> None:
    """The forms the documentation advertises all validate."""
    for schedule in ("*/5 * * * *", "0 7 * * 1-5", "0 12 * * MON#2", "0 3 L * *"):
        assert await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": schedule}}
        ) == {"options": {"schedule": schedule}}


async def test_it_fires_when_the_schedule_comes_round(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The automation runs at the scheduled minute, and not before."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 11:58:00")))
    ran = await _automation(hass, "0 * * * *")

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not ran

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(ran) == 1

    await _detach(hass)


async def test_it_keeps_firing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Each run lines up the one after it, rather than firing once and stopping."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 11:59:30")))
    ran = await _automation(hass, "*/1 * * * *")

    minutes = 3
    for _ in range(minutes):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert len(ran) == minutes

    await _detach(hass)


async def test_an_impossible_date_is_refused(hass: HomeAssistant) -> None:
    """The 30th of February is caught while parsing, and named as such."""
    with pytest.raises(vol.Invalid, match="Bad day-of-month"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": "0 0 30 2 *"}}
        )


@pytest.mark.parametrize("schedule", ["0 0 */20 * 1L", "0 0 */20 * 5#5"])
async def test_a_schedule_that_never_comes_round_is_refused(
    hass: HomeAssistant,
    schedule: str,
) -> None:
    """An expression that parses but never fires is refused as well.

    `0 0 */20 * 1L` asks for the 1st or the 21st, and for the last Monday of
    the month, which falls no earlier than the 22nd (a 28-day February, such
    as 2021). cronsim parses it happily and then produces nothing at all, so
    validation has to advance the iterator once to find out. Otherwise the
    automation loads, sits there and never runs, with nothing anywhere saying
    why.
    """
    with pytest.raises(vol.Invalid, match="never comes round"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"schedule": schedule}}
        )


async def test_a_date_years_away_is_fine(hass: HomeAssistant) -> None:
    """The 29th of February resolves to the next leap year, not to nothing."""
    trigger = SpookTrigger(hass, _config("0 0 29 2 *"))
    # pylint: disable-next=protected-access
    upcoming = trigger._next(dt_util.parse_datetime("2026-08-27 12:00:00"))  # noqa: SLF001

    assert upcoming is not None
    assert (upcoming.year, upcoming.month, upcoming.day) == (2028, 2, 29)


def _recording_tracker(
    bookings: list[tuple[datetime, Callable[[datetime], None]]],
) -> Callable[..., Callable[[], None]]:
    """Stand in for `async_track_point_in_time` and note what it was asked for.

    The trigger books a single absolute instant at a time, and most of what
    is worth checking is which instant that was. Going through the harness'
    own timers cannot show that.
    """

    def _track(_hass, action, point_in_time):  # noqa: ANN001, ANN202
        bookings.append((point_in_time, action))
        return lambda: None

    return _track


async def test_a_late_run_does_not_work_through_what_it_missed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After a clock jump the trigger looks forward, not back.

    Core hands the callback the time the run was scheduled for, not the time
    the timer got round to it. Those come apart when the machine has been
    asleep, and continuing from the scheduled time would work through every
    minute that was missed, one automation run each.

    The test harness cannot reproduce that with its own timers, so this drives
    the trigger's callback directly and checks what it asks for next.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))

    booked: list[tuple[datetime, Callable[[datetime], None]]] = []
    ran: list[dict] = []

    with patch(f"{CRON_MODULE}.async_track_point_in_time", _recording_tracker(booked)):
        trigger = SpookTrigger(hass, _config("*/1 * * * *"))
        await trigger.async_attach_runner(
            lambda payload, _description: ran.append(payload)
        )

        upcoming, fire = booked.pop()
        assert upcoming == dt_util.parse_datetime("2026-08-27 12:01:00").replace(
            tzinfo=upcoming.tzinfo
        )

        # An hour asleep. The timer only gets round to the 12:01 run now, and
        # is handed 12:01 as its argument.
        freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 13:00:00")))
        fire(dt_util.as_utc(upcoming))

    following, _ = booked.pop()
    assert following > dt_util.now(), (
        "asked for a time in the past, so it will catch up"
    )
    assert (following.hour, following.minute) == (13, 1)

    assert len(ran) == 1
    assert ran[0]["now"] == dt_util.now()


async def test_day_of_month_and_day_of_week_combine_with_or(
    hass: HomeAssistant,
) -> None:
    """Both day fields given means "or", which is what the documentation says.

    The classic crontab trap, and cronsim follows it: `0 0 15 * 1` fires on
    every Monday and on the 15th. This pins the behaviour the documentation
    describes, so a change in cronsim shows up here rather than in somebody's
    automation.
    """
    trigger = SpookTrigger(hass, _config("0 0 15 * 1"))
    moment = dt_util.parse_datetime("2026-01-01 00:00:00")

    days = []
    for _ in range(6):
        # pylint: disable-next=protected-access
        moment = trigger._next(moment)  # noqa: SLF001
        assert moment is not None
        days.append((moment.day, moment.weekday()))

    # A Monday that is not the 15th, and a 15th that is not a Monday. Merely
    # finding a Monday and finding a 15th would also hold for an "and", where
    # every occurrence is both at once.
    mondays_other_than_the_15th = [
        day for day, weekday in days if weekday == MONDAY and day != FIFTEENTH
    ]
    fifteenths_other_than_mondays = [
        day for day, weekday in days if day == FIFTEENTH and weekday != MONDAY
    ]

    assert mondays_other_than_the_15th, 'only ever the 15th, so this is an "and"'
    assert fifteenths_other_than_mondays, 'only ever a Monday, so this is an "and"'


@pytest.mark.parametrize(
    ("schedule", "days", "cron_weekdays"),
    [
        ("0 0 15 * */2", {15}, {0, 2, 4, 6}),
        ("0 0 */20 * 1", {1, 21}, {1}),
    ],
)
async def test_a_starred_day_field_combines_with_and(
    hass: HomeAssistant,
    schedule: str,
    days: set[int],
    cron_weekdays: set[int],
) -> None:
    """Let either day field start with `*` and the "or" turns into an "and".

    `0 0 15 * */2` is the 15th, but only when it lands on one of the days
    `*/2` picks out. Both directions are pinned, because this is the half of
    the rule that is easy to state the wrong way round.
    """
    trigger = SpookTrigger(hass, _config(schedule))
    moment = dt_util.parse_datetime("2026-01-01 00:00:00")

    for _ in range(8):
        # pylint: disable-next=protected-access
        moment = trigger._next(moment)  # noqa: SLF001
        assert moment is not None
        assert moment.day in days

        # cron counts Sunday as 0; `weekday()` counts Monday as 0.
        assert (moment.weekday() + 1) % 7 in cron_weekdays


async def test_a_time_zone_change_reworks_the_pending_wait(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Change the time zone and the wait already booked is worked out again.

    The wait is one absolute instant. Booked in US/Pacific, `0 7 * * *` means
    07:00 Pacific; switch to Europe/Amsterdam and that same instant is no
    longer seven in the morning anywhere the user cares about. Core's utility
    meter rebuilds its cronsim schedule on this event too.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))

    booked: list[tuple[datetime, Callable[[datetime], None]]] = []

    with patch(f"{CRON_MODULE}.async_track_point_in_time", _recording_tracker(booked)):
        trigger = SpookTrigger(hass, _config("0 7 * * *"))
        unattach = await trigger.async_attach_runner(lambda *_args: None)

        first, _ = booked.pop()
        assert first.hour == MORNING_SEVEN

        await hass.config.async_update(time_zone="Europe/Amsterdam")
        await hass.async_block_till_done()

        reworked, _ = booked.pop()
        unattach()

    assert reworked != first, "the wait was left on the old zone's instant"
    assert str(reworked.tzinfo) == "Europe/Amsterdam"
    assert reworked.hour == MORNING_SEVEN


async def test_an_unrelated_core_config_change_is_left_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The event fires for any core config change, so only the zone counts.

    Rebooking on every one of them would be harmless but pointless, and it
    would move the wait around whenever somebody renames their house.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))

    booked: list[tuple[datetime, Callable[[datetime], None]]] = []

    with patch(f"{CRON_MODULE}.async_track_point_in_time", _recording_tracker(booked)):
        trigger = SpookTrigger(hass, _config("0 7 * * *"))
        unattach = await trigger.async_attach_runner(lambda *_args: None)

        assert len(booked) == 1

        await hass.config.async_update(location_name="Somewhere else")
        await hass.async_block_till_done()

        unattach()

    assert len(booked) == 1, "rebooked over a change that was not the time zone"


def _config(schedule: str) -> TriggerConfig:
    """Build a trigger config, the way core hands one over."""
    return TriggerConfig(key="spook.cron", options={"schedule": schedule})
