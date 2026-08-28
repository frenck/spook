"""Tests for the spook.integration_failed trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.integration_failed import (
    SpookTrigger,
)
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

TWO_SPELLS = 2


def _entry(
    hass: HomeAssistant, domain: str = "demo", title: str = "Demo"
) -> MockConfigEntry:
    """Add a config entry that is loaded and happy."""
    entry = MockConfigEntry(domain=domain, title=title)
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


async def _automation(hass: HomeAssistant, options: dict) -> list[dict]:
    """Set up an automation on the trigger and record every run."""
    ran: list[dict] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(dict(call.data))

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "integration broke",
                    "trigger": {
                        "platform": "spook.integration_failed",
                        "options": options,
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "domain": "{{ trigger.domain }}",
                                "state": "{{ trigger.state }}",
                                "reason": "{{ trigger.reason }}",
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def _detach(hass: HomeAssistant) -> None:
    """Turn the automation off, which detaches its trigger."""
    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.integration_broke"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "integration_failed" in await async_get_triggers(hass)


async def test_a_duration_is_required(hass: HomeAssistant) -> None:
    """Without a duration there is no telling when trouble counts."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(hass, {"options": {}})


async def test_a_zero_duration_is_refused(hass: HomeAssistant) -> None:
    """Zero would put the deadline in the past, so it would never fire."""
    with pytest.raises(vol.Invalid, match="longer than zero"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"for": {"minutes": 0}}}
        )


async def test_it_fires_once_an_entry_stays_broken(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An entry that cannot set itself up for the whole duration is reported."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=14))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not ran

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["domain"] == "demo"
    assert ran[0]["state"] == "setup_retry"
    assert ran[0]["reason"] == "no route to host"

    await _detach(hass)


async def test_a_retry_cycle_does_not_restart_the_clock(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Retrying passes through `setup_in_progress`, which is not recovery.

    Home Assistant retries a failing entry on a backoff that tops out at ten
    minutes, and every attempt walks `setup_retry` to `setup_in_progress` and
    back. Counting that as recovery would reset the clock forever and nothing
    would ever be reported.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    await hass.async_block_till_done()

    # Three retries along the way, none of which get anywhere.
    for _ in range(3):
        freezer.tick(timedelta(minutes=4))
        entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
        entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "still no route")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1, "the retry cycle kept resetting the clock"

    await _detach(hass)


async def test_it_reports_the_failure_not_the_retry_in_progress(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The clock can run out mid-attempt, and `setup_in_progress` is no answer.

    A retrying entry is in `setup_in_progress` for the moment each attempt
    takes, with no reason attached. Reporting that would hand somebody a
    notification saying an integration is broken and then failing to say how.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=16))
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["state"] == "setup_retry"
    assert ran[0]["reason"] == "no route to host"

    await _detach(hass)


async def test_an_entry_that_recovers_in_time_is_not_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Trouble that sorts itself out is not trouble worth waking up for."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "hub still booting")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=5))
    entry.mock_state(hass, ConfigEntryState.LOADED)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not ran

    await _detach(hass)


@pytest.mark.parametrize(
    "state",
    [
        ConfigEntryState.SETUP_ERROR,
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.MIGRATION_ERROR,
        ConfigEntryState.FAILED_UNLOAD,
    ],
)
async def test_every_failed_state_counts(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    state: ConfigEntryState,
) -> None:
    """All four ways an entry can be broken are reported.

    `setup_retry` is the everyday one, but an entry can also fail outright,
    fail to migrate, or refuse to unload, and none of those fix themselves.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, state, "something went wrong")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1, f"{state.value} went unreported"
    assert ran[0]["state"] == state.value

    await _detach(hass)


@pytest.mark.parametrize(
    "state", [ConfigEntryState.LOADED, ConfigEntryState.NOT_LOADED]
)
async def test_a_healthy_state_is_not_a_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    state: ConfigEntryState,
) -> None:
    """Loaded is fine, and an entry you disabled yourself is fine too."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, state)
    await hass.async_block_till_done()

    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not ran

    await _detach(hass)


async def test_the_latest_reason_is_the_one_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Retries can say something more useful than the first attempt did.

    A hub coming up gives "connection refused" and then, once it answers,
    "invalid credentials". Reporting the first one would send somebody looking
    at their network when the problem is their password.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "connection refused")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=5))
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "invalid credentials")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["reason"] == "invalid credentials", "reported a stale reason"

    await _detach(hass)


async def test_it_fires_only_once_per_spell_of_trouble(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """One report per breakage, not one per retry."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    await hass.async_block_till_done()

    for _ in range(6):
        freezer.tick(timedelta(minutes=10))
        entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
        entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert len(ran) == 1, f"reported {len(ran)} times for one spell of trouble"

    await _detach(hass)


async def test_a_second_spell_of_trouble_is_reported_again(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """One report per spell, but a new spell is a new report.

    The other half of the once-only rule: an entry that recovers and then
    breaks again has to be heard from, or the trigger goes quiet for good
    after the first time it ever fires.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(ran) == 1

    # It comes back, and stays up for a while.
    entry.mock_state(hass, ConfigEntryState.LOADED)
    await hass.async_block_till_done()
    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(ran) == 1

    # And then it goes again.
    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == TWO_SPELLS, (
        "went quiet after the first report and never came back"
    )

    await _detach(hass)


async def test_an_entry_already_broken_is_picked_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Breakage from before the automation loaded still counts.

    An entry stuck in `setup_error` never announces itself again, so waiting
    for a change would mean never hearing about it.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_ERROR, "bad credentials")

    ran = await _automation(hass, {"for": "00:15:00"})

    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["state"] == "setup_error"

    await _detach(hass)


async def test_a_removed_entry_is_forgotten(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Deleting a broken integration is a fix, not a failure."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    entry = _entry(hass)

    ran = await _automation(hass, {"for": "00:15:00"})

    entry.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=5))
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not ran, "reported an entry that had been deleted"

    await _detach(hass)


async def test_only_the_named_entries_are_watched(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Naming entries limits it to those, and leaves the rest alone."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    watched = _entry(hass, domain="alarm", title="Alarm")
    ignored = _entry(hass, domain="doorbell", title="Doorbell")

    ran = await _automation(hass, {"for": "00:15:00", "entry_id": [watched.entry_id]})

    ignored.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    watched.mock_state(hass, ConfigEntryState.SETUP_RETRY, "panel unreachable")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [run["domain"] for run in ran] == ["alarm"]

    await _detach(hass)


async def test_every_entry_is_watched_when_none_are_named(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Leaving the filter out watches the lot, each reported on its own."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-28 12:00:00")))
    first = _entry(hass, domain="alarm", title="Alarm")
    second = _entry(hass, domain="doorbell", title="Doorbell")

    ran = await _automation(hass, {"for": "00:15:00"})

    first.mock_state(hass, ConfigEntryState.SETUP_RETRY, "panel unreachable")
    second.mock_state(hass, ConfigEntryState.SETUP_RETRY, "no route to host")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=16))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert sorted(run["domain"] for run in ran) == ["alarm", "doorbell"]

    await _detach(hass)
