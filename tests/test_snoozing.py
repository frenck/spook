"""Tests for snoozing automations."""

# The register's own bookkeeping is what one of these is about, and there is no
# public way at it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.components.automation import AutomationEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE
from homeassistant.core import Context, CoreState, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache,
)

from custom_components.spook.snoozing import (
    STORAGE_KEY,
    STORAGE_VERSION,
    Snoozing,
    async_setup_snoozing,
)

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory
    import pytest

    from homeassistant.helpers import entity_registry as er

    from homeassistant.core import Event, HomeAssistant
    from homeassistant.helpers.event import EventStateChangedData

SLEEPER = "automation.sleeper"
OTHER = "automation.other"
AN_HOUR = timedelta(hours=1)

CONFIG = {
    "automation": [
        {
            "id": "sleeper",
            "alias": "Sleeper",
            "triggers": [{"trigger": "state", "entity_id": "input_boolean.x"}],
            "actions": [],
        },
        {
            "id": "other",
            "alias": "Other",
            "triggers": [{"trigger": "state", "entity_id": "input_boolean.x"}],
            "actions": [],
        },
    ]
}


async def _automations(hass: HomeAssistant) -> None:
    """Set up the automations these tests snooze."""
    assert await async_setup_component(hass, "automation", CONFIG)
    await hass.async_block_till_done()


async def _register(hass: HomeAssistant) -> Snoozing:
    """Start a register, the way the config entry does."""
    hass.set_state(CoreState.running)
    await async_setup_snoozing(hass)
    return hass.data["spook_snoozing"]


async def _pass(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, amount: timedelta
) -> None:
    """Let a stretch of time go by.

    `freezer.tick` moves the clock, so the moment to fire at is the moment it
    now is. Adding the same stretch again moves twice as far.
    """
    freezer.tick(amount)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_it_turns_the_automation_off(hass: HomeAssistant) -> None:
    """Which is the only way to make an automation stop for a while."""
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)

    assert hass.states.get(SLEEPER).state == "off"
    assert snoozing.async_until(SLEEPER) is not None

    snoozing.async_stop()


async def test_it_turns_the_automation_back_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """And that is the half an automation cannot do for itself."""
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    assert hass.states.get(SLEEPER).state == "off"

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "on"
    assert snoozing.async_until(SLEEPER) is None

    snoozing.async_stop()


async def test_it_leaves_others_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Snoozing one automation is not snoozing the house."""
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)

    assert hass.states.get(OTHER).state == "on"

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(OTHER).state == "on"

    snoozing.async_stop()


async def test_an_automation_already_off_is_not_snoozed(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Waking it would turn on something somebody deliberately turned off."""
    await _automations(hass)
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": SLEEPER}, blocking=True
    )
    await hass.async_block_till_done()

    snoozing = await _register(hass)
    await snoozing.async_snooze(SLEEPER, AN_HOUR)

    assert snoozing.async_until(SLEEPER) is None
    assert "did not snooze" in caplog.text, "it went quiet about doing nothing"

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(SLEEPER).state == "off", "it turned on anyway"

    snoozing.async_stop()


async def test_turning_it_on_by_hand_cancels_the_snooze(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Somebody turning it on says more than a wake-up time set earlier."""
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)

    await hass.services.async_call(
        "automation", "turn_on", {"entity_id": SLEEPER}, blocking=True
    )
    await hass.async_block_till_done()

    assert snoozing.async_until(SLEEPER) is None, "it is still counting down"

    # And it is not turned off again, nor woken a second time.
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": SLEEPER}, blocking=True
    )
    await hass.async_block_till_done()
    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "off", "the cancelled snooze woke it"

    snoozing.async_stop()


async def test_snoozing_again_replaces_the_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Asking for longer means longer, not two answers."""
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    first = snoozing.async_until(SLEEPER)

    await snoozing.async_snooze(SLEEPER, AN_HOUR * 3)
    second = snoozing.async_until(SLEEPER)
    assert second > first

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(SLEEPER).state == "off", "the first wait still woke it"

    await _pass(hass, freezer, AN_HOUR * 2)
    assert hass.states.get(SLEEPER).state == "on"

    snoozing.async_stop()


async def test_it_is_written_down(hass: HomeAssistant, hass_storage: dict) -> None:
    """Because the automation stays off across a restart and this must not."""
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)

    stored = hass_storage[STORAGE_KEY]
    assert stored["version"] == STORAGE_VERSION
    assert SLEEPER in stored["data"]

    snoozing.async_stop()


async def test_a_snooze_that_outlived_the_restart_is_picked_up(
    hass: HomeAssistant,
    hass_storage: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Still asleep, and still owed a wake-up call."""
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: until.isoformat()},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    snoozing = await _register(hass)
    assert hass.states.get(SLEEPER).state == "off"

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(SLEEPER).state == "on", "it never woke up"

    snoozing.async_stop()


async def test_a_snooze_that_expired_while_down_wakes_at_once(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """The time passed with nobody watching, which still counts."""
    until = dt_util.utcnow() - AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: until.isoformat()},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    snoozing = await _register(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", "it slept through its alarm"
    assert snoozing.async_until(SLEEPER) is None

    snoozing.async_stop()


async def test_a_snooze_for_something_turned_on_while_down_is_dropped(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Somebody turned it on, which settles it."""
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: until.isoformat()},
    }
    await _automations(hass)
    assert hass.states.get(SLEEPER).state == "on"

    snoozing = await _register(hass)
    await hass.async_block_till_done()

    assert snoozing.async_until(SLEEPER) is None, "it is still counting down"
    assert hass.states.get(SLEEPER).state == "on"

    snoozing.async_stop()


async def test_a_snooze_for_something_that_is_gone_is_dropped(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """An automation deleted while Home Assistant was down."""
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {"automation.deleted": until.isoformat()},
    }
    await _automations(hass)

    snoozing = await _register(hass)
    await hass.async_block_till_done()

    assert snoozing.async_until("automation.deleted") is None

    snoozing.async_stop()


async def test_it_waits_for_home_assistant_to_finish_starting(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """The automations have to exist before anything can be woken.

    Set up during startup, the register holds off until Home Assistant says it
    has finished, because turning on an automation that is not there yet does
    nothing at all.
    """
    until = dt_util.utcnow() - AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: until.isoformat()},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))

    hass.set_state(CoreState.starting)
    await async_setup_snoozing(hass)
    snoozing = hass.data["spook_snoozing"]

    # Nothing has happened yet: the automations are not up.
    assert snoozing.async_until(SLEEPER) is not None

    await _automations(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", "it never caught up"

    snoozing.async_stop()


async def test_stopping_leaves_the_snooze_written_down(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Unloading Spook is not a reason to wake everything up.

    It is also not a reason to forget: the automation is still off, so the
    record is what brings it back next time.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    snoozing.async_stop()

    assert hass.states.get(SLEEPER).state == "off"
    assert SLEEPER in hass_storage[STORAGE_KEY]["data"]


async def test_the_caller_is_carried_into_the_turning_off(
    hass: HomeAssistant,
) -> None:
    """Whoever asked for the snooze is who turned the automation off.

    The action passing its caller down is pinned where the action lives; this
    is the half underneath it.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    asked = Context()
    await snoozing.async_snooze(SLEEPER, AN_HOUR, context=asked)

    assert hass.states.get(SLEEPER).context.id == asked.id

    snoozing.async_stop()


async def test_a_wake_that_fails_keeps_the_record(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Because forgetting it is what turns a snooze into a disable.

    An automation left off with nothing written down is exactly the failure
    this whole thing exists to prevent, so the record only goes once turning
    it on has actually worked.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)

    with patch.object(
        AutomationEntity,
        "async_turn_on",
        side_effect=HomeAssistantError("no"),
    ):
        await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert snoozing.async_until(SLEEPER) is not None, (
        "the record went even though it never woke"
    )
    assert hass.states.get(SLEEPER).state == "off"
    assert "could not wake" in caplog.text, "it failed quietly"

    snoozing.async_stop()


async def test_an_automation_that_is_deleted_takes_its_snooze_with_it(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Because a record for something that no longer exists is dead weight.

    Read off the registry rather than off a state going missing, which a
    rename does just as thoroughly as a delete.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    assert snoozing.async_until(SLEEPER) is not None

    entity_registry.async_remove(SLEEPER)
    await hass.async_block_till_done()

    assert snoozing.async_until(SLEEPER) is None, "the snooze outlived its automation"

    snoozing.async_stop()


async def test_renaming_an_automation_leaves_no_record_under_either_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A snooze follows the automation, not the name it had that day.

    Measured rather than assumed: Home Assistant brings a renamed automation
    back on, because the new entity ID has nothing to restore from. So the
    snooze ends there anyway, the way any other turning-on ends one. What the
    registry buys is that nothing stays filed under the old name, counting
    down towards an entity nobody uses.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    assert snoozing.async_until(SLEEPER) is not None

    renamed = "automation.now_called_this"
    entity_registry.async_update_entity(SLEEPER, new_entity_id=renamed)
    await hass.async_block_till_done()

    assert hass.states.get(renamed).state == "on"
    assert snoozing.async_until(SLEEPER) is None, "a record left under the old name"
    assert snoozing.async_until(renamed) is None

    snoozing.async_stop()


async def test_an_automation_that_is_merely_away_keeps_its_snooze(
    hass: HomeAssistant,
) -> None:
    """A reload passes through unavailable, and must not read as a delete."""
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    until = snoozing.async_until(SLEEPER)

    hass.states.async_set(SLEEPER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    assert snoozing.async_until(SLEEPER) == until, "a reload cancelled the snooze"

    snoozing.async_stop()


async def test_a_stale_wake_up_call_leaves_the_new_wait_alone(
    hass: HomeAssistant,
) -> None:
    """Cancelling a wait does not recall a callback already on its way.

    Driven straight, because arranging for a timer to fire after it was
    cancelled is a race. The callback is asked for at one time and then the
    wait is moved, which is what asking for longer does.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    first = snoozing.async_until(SLEEPER)
    stale = snoozing._async_due(SLEEPER, first)

    await snoozing.async_snooze(SLEEPER, AN_HOUR * 3)
    later = snoozing.async_until(SLEEPER)

    # The wait it belonged to is gone, so it has nothing to say.
    await stale(dt_util.utcnow())

    assert snoozing.async_until(SLEEPER) == later, "it dropped the newer wait"
    assert hass.states.get(SLEEPER).state == "off", "it woke at the old time"

    snoozing.async_stop()


async def test_unloading_while_the_store_is_read_leaves_nothing_behind(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Stopping cannot reach into a coroutine that is waiting on something.

    So the two are made to genuinely overlap here: the read is held open, the
    register is stopped, and only then is the read let go. A test that awaits
    the start first would pass against exactly the leak it is named for.
    """
    until = dt_util.utcnow() - AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: until.isoformat()},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    hass.set_state(CoreState.running)
    snoozing = Snoozing(hass)

    reading = asyncio.Event()
    let_go = asyncio.Event()
    real_load = Store.async_load

    async def _held_open(self: Store) -> dict | None:
        reading.set()
        await let_go.wait()
        return await real_load(self)

    with patch.object(Store, "async_load", _held_open):
        starting = hass.async_create_task(snoozing.async_start())

        async with asyncio.timeout(5):
            await reading.wait()

        snoozing.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await starting

    await hass.async_block_till_done()

    assert not snoozing._timers, "it armed a timer on a stopped register"
    assert snoozing._unsub_watching is None, "it left a listener behind"
    assert hass.states.get(SLEEPER).state == "off", (
        "it woke an automation after Spook was unloaded"
    )


async def test_a_snooze_shorter_than_its_own_turning_off_still_ends_on(
    hass: HomeAssistant,
) -> None:
    """A wake must not overtake the disable it belongs to.

    The turning-off is held open here and the snooze made shorter than it, so
    the deadline is certain to pass while the automation is still being turned
    off. Arming the timer before that would wake it first and disable it
    second: off, with nothing written down.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    turning_off = asyncio.Event()
    let_go = asyncio.Event()
    back_on = asyncio.Event()
    real_turn_off = AutomationEntity.async_turn_off

    @callback
    def _woken(event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state is not None and new_state.state == "on":
            back_on.set()

    unsub = async_track_state_change_event(hass, [SLEEPER], _woken)

    async def _held_open(self: AutomationEntity, **kwargs: object) -> None:
        turning_off.set()
        await let_go.wait()

        await real_turn_off(self, **kwargs)

    with patch.object(AutomationEntity, "async_turn_off", _held_open):
        snoozed = hass.async_create_task(
            snoozing.async_snooze(SLEEPER, timedelta(milliseconds=1))
        )

        async with asyncio.timeout(5):
            await turning_off.wait()

        # Well past a millisecond, so the deadline is behind us by the time
        # the automation is actually off.
        await asyncio.sleep(0.05)
        let_go.set()

        async with asyncio.timeout(5):
            await snoozed

    async with asyncio.timeout(5):
        await back_on.wait()

    unsub()

    assert snoozing.async_until(SLEEPER) is None, "it left a wake-up time behind"

    snoozing.async_stop()


async def test_turning_it_on_while_a_longer_snooze_saves_wins(
    hass: HomeAssistant,
) -> None:
    """Extending a snooze is the one moment the automation is off and watched.

    Turning it on there cancels the snooze, and the extension must not then
    turn it off again: that is an automation left off with nothing written
    down to wake it, which is the whole failure this exists to prevent.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    assert hass.states.get(SLEEPER).state == "off"

    saving = asyncio.Event()
    let_go = asyncio.Event()
    real_save = Store.async_save

    async def _held_open(self: Store, data: dict) -> None:
        saving.set()
        await let_go.wait()
        await real_save(self, data)

    with patch.object(Store, "async_save", _held_open):
        extending = hass.async_create_task(snoozing.async_snooze(SLEEPER, AN_HOUR * 3))

        async with asyncio.timeout(5):
            await saving.wait()

        # Not waited on any further than the call itself: the listener that
        # cancels the snooze is a callback, so it has already run, and its own
        # save is queued behind the one being held open here.
        await hass.services.async_call(
            "automation", "turn_on", {"entity_id": SLEEPER}, blocking=True
        )
        let_go.set()

        async with asyncio.timeout(5):
            await extending

    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", (
        "the extension turned it off again after being cancelled"
    )
    assert snoozing.async_until(SLEEPER) is None, "and left a wake-up time behind"

    snoozing.async_stop()


async def test_a_wake_that_fails_writes_the_record_back_down(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """In memory is not enough, because somebody else may save in between.

    A snooze for another automation writes out the whole register, and by then
    this record has already left it. Putting it back only in memory means a
    restart loses it, and the automation is off for good: the exact thing this
    is here to prevent.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    until = snoozing.async_until(SLEEPER)

    waking = asyncio.Event()
    let_go = asyncio.Event()

    async def _refuse(_self: AutomationEntity, **_kwargs: object) -> None:
        waking.set()
        await let_go.wait()

        msg = "no"
        raise HomeAssistantError(msg)

    with patch.object(AutomationEntity, "async_turn_on", _refuse):
        # Driven straight rather than through the clock, so the failing wake
        # and the snooze below genuinely overlap.
        failing = hass.async_create_task(snoozing._async_wake(SLEEPER, until))

        async with asyncio.timeout(5):
            await waking.wait()

        # Writes out a register that no longer has the one being woken in it.
        await snoozing.async_snooze(OTHER, AN_HOUR)
        assert SLEEPER not in hass_storage[STORAGE_KEY]["data"]

        let_go.set()

        async with asyncio.timeout(5):
            await failing

    await hass.async_block_till_done()

    assert snoozing.async_until(SLEEPER) is not None
    assert SLEEPER in hass_storage[STORAGE_KEY]["data"], (
        "the record lives only in memory, so a restart would lose it"
    )

    snoozing.async_stop()


async def test_a_wake_up_call_that_came_due_at_the_unload_does_nothing(
    hass: HomeAssistant,
) -> None:
    """Cancelling a timer does not recall a callback that already fired.

    Driven straight, because a callback firing in the same breath as the
    unload is a race, and a test that lets the two miss each other would pass
    against exactly the leak it is named for. The snooze keeps its record, so
    the next start sees to it.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    until = snoozing.async_until(SLEEPER)
    already_going = snoozing._async_due(SLEEPER, until)

    snoozing.async_stop()
    await already_going(dt_util.utcnow())
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "off", (
        "it woke an automation after Spook was unloaded"
    )
    assert snoozing.async_until(SLEEPER) == until, "and forgot the snooze on the way"


async def test_turning_one_on_while_catching_up_cancels_its_snooze(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Catching up ends in a store write, and somebody may act during it.

    Nothing here is overdue, so no wake sets up the watch along the way, and
    the write at the end is the whole window. Turning an automation on cancels
    its snooze, and a start still tidying up must not be the moment that
    stops being true.
    """
    later = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: later.isoformat()},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    hass.set_state(CoreState.running)
    snoozing = Snoozing(hass)

    saving = asyncio.Event()
    let_go = asyncio.Event()
    real_save = Store.async_save

    async def _held_open(self: Store, data: dict) -> None:
        saving.set()
        await let_go.wait()

        await real_save(self, data)

    with patch.object(Store, "async_save", _held_open):
        starting = hass.async_create_task(snoozing.async_start())

        async with asyncio.timeout(5):
            await saving.wait()

        # Somebody decides they want it running again.
        await hass.services.async_call(
            "automation", "turn_on", {"entity_id": SLEEPER}, blocking=True
        )
        let_go.set()

        async with asyncio.timeout(5):
            await starting

    await hass.async_block_till_done()

    assert snoozing.async_until(SLEEPER) is None, (
        "it kept counting down for one somebody had turned back on"
    )
    assert SLEEPER not in snoozing._timers, "and left its wake-up call armed"

    snoozing.async_stop()


async def test_unloading_partway_through_catching_up_stops_there(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Two overdue snoozes, and Spook goes while the first is being woken.

    The second must stay asleep rather than be turned on by a register that
    is no longer running. It keeps its record, so the next start sees to it.
    """
    until = dt_util.utcnow() - AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: until.isoformat(), OTHER: until.isoformat()},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"), State(OTHER, "off")))
    await _automations(hass)

    hass.set_state(CoreState.running)
    snoozing = Snoozing(hass)

    waking = asyncio.Event()
    let_go = asyncio.Event()
    real_turn_on = AutomationEntity.async_turn_on

    async def _held_open(self: AutomationEntity, **kwargs: object) -> None:
        if self.entity_id == SLEEPER:
            waking.set()
            await let_go.wait()

        await real_turn_on(self, **kwargs)

    with patch.object(AutomationEntity, "async_turn_on", _held_open):
        starting = hass.async_create_task(snoozing.async_start())

        async with asyncio.timeout(5):
            await waking.wait()

        snoozing.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await starting

    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", "the one it was on never woke"
    assert hass.states.get(OTHER).state == "off", (
        "it kept waking automations after Spook was unloaded"
    )
    assert snoozing.async_until(OTHER) is not None, "and forgot the one it skipped"


async def test_unloading_while_the_store_is_read_before_the_start(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Same overlap, with Home Assistant not up yet.

    A register that is still reading its store when Spook goes would otherwise
    sit down to wait for a start event nobody is going to unsubscribe it from.
    """
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: until.isoformat()},
    }
    await _automations(hass)

    hass.set_state(CoreState.not_running)
    snoozing = Snoozing(hass)

    reading = asyncio.Event()
    let_go = asyncio.Event()
    real_load = Store.async_load

    async def _held_open(self: Store) -> dict | None:
        reading.set()
        await let_go.wait()
        return await real_load(self)

    with patch.object(Store, "async_load", _held_open):
        starting = hass.async_create_task(snoozing.async_start())

        async with asyncio.timeout(5):
            await reading.wait()

        snoozing.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await starting

    assert snoozing._unsub_started is None, "it waited for a start after unloading"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert not snoozing._timers, "the start it waited for armed a timer"


async def test_unloading_while_a_snooze_is_saved_still_leaves_nothing_behind(
    hass: HomeAssistant,
) -> None:
    """The other side of the same thing: a call in flight when the entry goes.

    The automation is still turned off, because the snooze is written down by
    then and the next start picks it up. Only the waiting is dropped, there
    being nobody left to do it.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    saving = asyncio.Event()
    let_go = asyncio.Event()
    real_save = Store.async_save

    async def _held_open(self: Store, data: dict) -> None:
        saving.set()
        await let_go.wait()
        await real_save(self, data)

    with patch.object(Store, "async_save", _held_open):
        snoozed = hass.async_create_task(snoozing.async_snooze(SLEEPER, AN_HOUR))

        async with asyncio.timeout(5):
            await saving.wait()

        snoozing.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await snoozed

    await hass.async_block_till_done()

    assert not snoozing._timers, "it armed a timer on a stopped register"
    assert snoozing._unsub_watching is None, "it left a listener behind"
    assert snoozing._unsub_registry is None, "it kept watching the registry"
    assert hass.states.get(SLEEPER).state == "off", "it did not turn it off at all"
