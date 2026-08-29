"""Tests for holding automations in a state for a while."""

# The register's own bookkeeping is what one of these is about, and there is no
# public way at it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
import asyncio
import contextlib
from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.components.automation import AutomationEntity
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Context, CoreState, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache,
)

from custom_components.spook.timed_states import (
    LEGACY_STORAGE_KEY,
    STORAGE_KEY,
    STORAGE_VERSION,
    TimedStates,
    _Held,
    async_setup_timed_states,
)

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from datetime import datetime

    from freezegun.api import FrozenDateTimeFactory

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


NAMELESS = {
    "automation": [
        {"alias": "Nameless", "triggers": [], "actions": [{"delay": 1}]},
        {"alias": "Also nameless", "triggers": [], "actions": [{"delay": 1}]},
    ]
}


def _without_the_nameless_one() -> dict:
    """Return the same config with the first one taken out."""
    return {"automation": NAMELESS["automation"][1:]}


def _record(until: datetime, state: str = STATE_OFF) -> dict[str, str]:
    """Return one stored record, in the shape the store keeps them."""
    return {"until": until.isoformat(), "state": state}


async def _automations(hass: HomeAssistant) -> None:
    """Set up the automations these tests snooze."""
    assert await async_setup_component(hass, "automation", CONFIG)
    await hass.async_block_till_done()


async def _register(hass: HomeAssistant) -> TimedStates:
    """Start a register, the way the config entry does."""
    hass.set_state(CoreState.running)
    await async_setup_timed_states(hass)
    return hass.data["spook_timed_states"]


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
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    assert hass.states.get(SLEEPER).state == "off"
    assert timed_states.async_until(SLEEPER) is not None

    timed_states.async_stop()


async def test_it_turns_the_automation_back_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """And that is the half an automation cannot do for itself."""
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    assert hass.states.get(SLEEPER).state == "off"

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "on"
    assert timed_states.async_until(SLEEPER) is None

    timed_states.async_stop()


async def test_it_leaves_others_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Holding one automation is not holding the house."""
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    assert hass.states.get(OTHER).state == "on"

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(OTHER).state == "on"

    timed_states.async_stop()


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

    timed_states = await _register(hass)
    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    assert timed_states.async_until(SLEEPER) is None
    assert "left automation.sleeper alone" in caplog.text, (
        "it went quiet about doing nothing"
    )

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(SLEEPER).state == "off", "it turned on anyway"

    timed_states.async_stop()


async def test_turning_it_on_by_hand_cancels_the_snooze(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Somebody turning it on says more than a wake-up time set earlier."""
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    await hass.services.async_call(
        "automation", "turn_on", {"entity_id": SLEEPER}, blocking=True
    )
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is None, "it is still counting down"

    # And it is not turned off again, nor woken a second time.
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": SLEEPER}, blocking=True
    )
    await hass.async_block_till_done()
    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "off", "the cancelled snooze woke it"

    timed_states.async_stop()


async def test_holding_again_replaces_the_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Asking for longer means longer, not two answers."""
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    first = timed_states.async_until(SLEEPER)

    await timed_states.async_hold(SLEEPER, AN_HOUR * 3, STATE_OFF)
    second = timed_states.async_until(SLEEPER)
    assert second > first

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(SLEEPER).state == "off", "the first wait still woke it"

    await _pass(hass, freezer, AN_HOUR * 2)
    assert hass.states.get(SLEEPER).state == "on"

    timed_states.async_stop()


async def test_it_is_written_down(hass: HomeAssistant, hass_storage: dict) -> None:
    """Because the automation stays off across a restart and this must not."""
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    stored = hass_storage[STORAGE_KEY]
    assert stored["version"] == STORAGE_VERSION
    assert SLEEPER in stored["data"]

    timed_states.async_stop()


async def test_a_snooze_that_outlived_the_restart_is_picked_up(
    hass: HomeAssistant,
    hass_storage: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Still asleep, and still owed a wake-up call."""
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: _record(until)},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    timed_states = await _register(hass)
    assert hass.states.get(SLEEPER).state == "off"

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(SLEEPER).state == "on", "it never woke up"

    timed_states.async_stop()


async def test_a_snooze_that_expired_while_down_wakes_at_once(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """The time passed with nobody watching, which still counts."""
    until = dt_util.utcnow() - AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: _record(until)},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    timed_states = await _register(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", "it slept through its alarm"
    assert timed_states.async_until(SLEEPER) is None

    timed_states.async_stop()


async def test_a_snooze_for_something_turned_on_while_down_is_dropped(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Somebody turned it on, which settles it."""
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: _record(until)},
    }
    await _automations(hass)
    assert hass.states.get(SLEEPER).state == "on"

    timed_states = await _register(hass)
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is None, "it is still counting down"
    assert hass.states.get(SLEEPER).state == "on"

    timed_states.async_stop()


async def test_a_snooze_for_something_that_is_gone_is_dropped(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """An automation deleted while Home Assistant was down."""
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {"automation.deleted": _record(until)},
    }
    await _automations(hass)

    timed_states = await _register(hass)
    await hass.async_block_till_done()

    assert timed_states.async_until("automation.deleted") is None

    timed_states.async_stop()


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
        "data": {SLEEPER: _record(until)},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))

    hass.set_state(CoreState.starting)
    await async_setup_timed_states(hass)
    timed_states = hass.data["spook_timed_states"]

    # Nothing has happened yet: the automations are not up.
    assert timed_states.async_until(SLEEPER) is not None

    await _automations(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", "it never caught up"

    timed_states.async_stop()


async def test_stopping_leaves_the_snooze_written_down(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Unloading Spook is not a reason to wake everything up.

    It is also not a reason to forget: the automation is still off, so the
    record is what brings it back next time.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    timed_states.async_stop()

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
    timed_states = await _register(hass)

    asked = Context()
    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF, context=asked)

    assert hass.states.get(SLEEPER).context.id == asked.id

    timed_states.async_stop()


async def test_turning_it_off_while_a_fresh_snooze_saves_gives_it_up(
    hass: HomeAssistant,
) -> None:
    """Spook does not wake what it did not put to sleep.

    A fresh snooze checks the automation is running before it writes anything
    down, and somebody can turn it off during that write. The turning-off
    below then changes nothing, and keeping the deadline would have Spook turn
    on an automation that a person deliberately disabled.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    saving = asyncio.Event()
    let_go = asyncio.Event()
    real_save = Store.async_save

    async def _held_open(self: Store, data: dict) -> None:
        saving.set()
        await let_go.wait()

        await real_save(self, data)

    with patch.object(Store, "async_save", _held_open):
        snoozed = hass.async_create_task(
            timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
        )

        async with asyncio.timeout(5):
            await saving.wait()

        await hass.services.async_call(
            "automation", "turn_off", {"entity_id": SLEEPER}, blocking=True
        )
        let_go.set()

        async with asyncio.timeout(5):
            await snoozed

    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is None, (
        "it claimed an automation somebody else turned off"
    )

    timed_states.async_stop()


async def test_a_second_chance_overtaken_by_a_person_does_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The second chance waits its turn, and things happen while it waits.

    Somebody turning the automation on cancels the snooze, and the wake that
    was queued before that must not go on to hand it back off.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    async def _skipped(_self: AutomationEntity, **_kwargs: object) -> None:
        return

    with patch.object(AutomationEntity, "async_turn_on", _skipped):
        await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert timed_states.async_until(SLEEPER) is not None

    # Back again, which queues the second chance, and a person gets there
    # first.
    hass.states.async_set(SLEEPER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    hass.states.async_set(SLEEPER, "off")
    await hass.services.async_call(
        "automation", "turn_on", {"entity_id": SLEEPER}, blocking=True
    )

    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", (
        "the queued wake handed it back off against the person who wanted it on"
    )
    assert timed_states.async_until(SLEEPER) is None

    timed_states.async_stop()


async def test_a_snooze_cancelled_after_it_took_still_wakes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A script calling this can be stopped mid-call, which is not a shutdown.

    Home Assistant carries on and never comes back to pick the record up, so
    an automation turned off by a cancelled snooze would stay off until a
    restart if nothing were waiting on its deadline.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    turned_off = asyncio.Event()
    real_turn_off = AutomationEntity.async_turn_off

    async def _then_hang(self: AutomationEntity, **kwargs: object) -> None:
        await real_turn_off(self, **kwargs)
        turned_off.set()

        await asyncio.Event().wait()

    with patch.object(AutomationEntity, "async_turn_off", _then_hang):
        snoozed = hass.async_create_task(
            timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
        )

        async with asyncio.timeout(5):
            await turned_off.wait()

        snoozed.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await snoozed

    assert hass.states.get(SLEEPER).state == "off"
    assert timed_states.async_until(SLEEPER) is not None

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "on", "nothing was waiting on it"

    timed_states.async_stop()


async def test_a_fresh_snooze_whose_turning_off_fails_leaves_no_record(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Nothing was snoozed, so there is nothing to wake later.

    Keeping the record would have Spook turn on an automation that somebody
    else turned off in the meantime, which is the one thing it promises not
    to do.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    with (
        patch.object(
            AutomationEntity,
            "async_turn_off",
            side_effect=HomeAssistantError("no"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    assert hass.states.get(SLEEPER).state == "on"
    assert timed_states.async_until(SLEEPER) is None, (
        "it wrote down a snooze for an automation it never turned off"
    )

    # Somebody turns it off themselves, and it is not Spook's to turn back on.
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": SLEEPER}, blocking=True
    )
    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "off", (
        "it woke an automation it had not put to sleep"
    )

    timed_states.async_stop()


async def test_an_extension_whose_turning_off_fails_still_wakes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The deadline is written down, so something has to be waiting on it.

    Extending a snooze lets go of the wait it had to make room for the new
    one, and that new wait is only set up once the automation is off. A
    failure in between used to leave a record with nothing waiting on it: an
    automation off until somebody restarts Home Assistant.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    with (
        patch.object(
            AutomationEntity,
            "async_turn_off",
            side_effect=HomeAssistantError("no"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await timed_states.async_hold(SLEEPER, AN_HOUR * 2, STATE_OFF)

    assert timed_states.async_until(SLEEPER) is not None

    await _pass(hass, freezer, AN_HOUR * 2 + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "on", "nothing was waiting on it"
    assert timed_states.async_until(SLEEPER) is None

    timed_states.async_stop()


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
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    with patch.object(
        AutomationEntity,
        "async_turn_on",
        side_effect=HomeAssistantError("no"),
    ):
        await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert timed_states.async_until(SLEEPER) is not None, (
        "the record went even though it never woke"
    )
    assert hass.states.get(SLEEPER).state == "off"
    assert "could not put" in caplog.text, "it failed quietly"

    timed_states.async_stop()


async def test_an_automation_that_is_deleted_takes_its_snooze_with_it(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Because a record for something that no longer exists is dead weight.

    Read off the registry rather than off a state going missing, which a
    rename does just as thoroughly as a delete.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    assert timed_states.async_until(SLEEPER) is not None

    entity_registry.async_remove(SLEEPER)
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is None, (
        "the snooze outlived its automation"
    )

    timed_states.async_stop()


async def test_an_automation_without_an_id_takes_its_snooze_with_it(
    hass: HomeAssistant,
) -> None:
    """A YAML automation written without an `id` has no registry entry.

    So there is no removal event to read, and a state gone for good is the
    only word there is. Measured: deleting one of these takes its state
    straight to nothing, where an automation with an `id` would linger as
    unavailable.
    """
    assert await async_setup_component(hass, "automation", NAMELESS)
    await hass.async_block_till_done()

    timed_states = await _register(hass)

    nameless = "automation.nameless"
    await timed_states.async_hold(nameless, AN_HOUR, STATE_OFF)
    assert timed_states.async_until(nameless) is not None

    with patch(
        "homeassistant.config.async_hass_config_yaml",
        return_value=_without_the_nameless_one(),
    ):
        await hass.services.async_call("automation", "reload", blocking=True)
        await hass.async_block_till_done()

    assert hass.states.get(nameless) is None
    assert timed_states.async_until(nameless) is None, (
        "the snooze outlived the automation it was for"
    )

    timed_states.async_stop()


async def test_a_state_that_goes_while_the_entity_stays_keeps_the_snooze(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A missing state is not proof on its own that an automation is gone.

    An entity that still has its registry entry is still an automation, and
    its snooze outlives whatever took the state away.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    until = timed_states.async_until(SLEEPER)

    assert entity_registry.async_get(SLEEPER) is not None
    hass.states.async_remove(SLEEPER)
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) == until, (
        "it read a missing state as an automation that no longer exists"
    )

    timed_states.async_stop()


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
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    assert timed_states.async_until(SLEEPER) is not None

    renamed = "automation.now_called_this"
    entity_registry.async_update_entity(SLEEPER, new_entity_id=renamed)
    await hass.async_block_till_done()

    assert hass.states.get(renamed).state == "on"
    assert timed_states.async_until(SLEEPER) is None, "a record left under the old name"
    assert timed_states.async_until(renamed) is None

    timed_states.async_stop()


async def test_an_automation_that_is_merely_away_keeps_its_snooze(
    hass: HomeAssistant,
) -> None:
    """A reload passes through unavailable, and must not read as a delete."""
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    until = timed_states.async_until(SLEEPER)

    hass.states.async_set(SLEEPER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) == until, "a reload cancelled the snooze"

    timed_states.async_stop()


async def test_a_stale_wake_up_call_leaves_the_new_wait_alone(
    hass: HomeAssistant,
) -> None:
    """Cancelling a wait does not recall a callback already on its way.

    Driven straight, because arranging for a timer to fire after it was
    cancelled is a race. The callback is asked for at one time and then the
    wait is moved, which is what asking for longer does.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    first = timed_states.async_until(SLEEPER)
    stale = timed_states._async_due(SLEEPER, _Held(first, STATE_OFF))

    await timed_states.async_hold(SLEEPER, AN_HOUR * 3, STATE_OFF)
    later = timed_states.async_until(SLEEPER)

    # The wait it belonged to is gone, so it has nothing to say.
    await stale(dt_util.utcnow())

    assert timed_states.async_until(SLEEPER) == later, "it dropped the newer wait"
    assert hass.states.get(SLEEPER).state == "off", "it woke at the old time"
    assert SLEEPER in timed_states._timers, (
        "it dropped the newer wait's timer, leaving nothing able to cancel it"
    )

    timed_states.async_stop()


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
        "data": {SLEEPER: _record(until)},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    hass.set_state(CoreState.running)
    timed_states = TimedStates(hass)

    reading = asyncio.Event()
    let_go = asyncio.Event()
    real_load = Store.async_load

    async def _held_open(self: Store) -> dict | None:
        reading.set()
        await let_go.wait()
        return await real_load(self)

    with patch.object(Store, "async_load", _held_open):
        starting = hass.async_create_task(timed_states.async_start())

        async with asyncio.timeout(5):
            await reading.wait()

        timed_states.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await starting

    await hass.async_block_till_done()

    assert not timed_states._timers, "it armed a timer on a stopped register"
    assert timed_states._unsub_watching is None, "it left a listener behind"
    assert hass.states.get(SLEEPER).state == "off", (
        "it woke an automation after Spook was unloaded"
    )


async def test_turning_it_on_while_the_snooze_turns_it_off_takes_it_back(
    hass: HomeAssistant,
) -> None:
    """The turning-off can be in flight when the snooze is cancelled.

    Extending a snooze checks the record before it turns the automation off,
    and somebody can turn it on between that check and the call landing. The
    disable then goes through against a snooze that no longer exists, so it
    has to be taken back: an automation off with nothing to wake it is the
    whole failure this prevents.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    turning_off = asyncio.Event()
    let_go = asyncio.Event()
    real_turn_off = AutomationEntity.async_turn_off

    async def _held_open(self: AutomationEntity, **kwargs: object) -> None:
        turning_off.set()
        await let_go.wait()

        await real_turn_off(self, **kwargs)

    with patch.object(AutomationEntity, "async_turn_off", _held_open):
        extending = hass.async_create_task(
            timed_states.async_hold(SLEEPER, AN_HOUR * 3, STATE_OFF)
        )

        async with asyncio.timeout(5):
            await turning_off.wait()

        await hass.services.async_call(
            "automation", "turn_on", {"entity_id": SLEEPER}, blocking=True
        )
        let_go.set()

        async with asyncio.timeout(5):
            await extending

    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", (
        "the disable went through against a snooze that had been cancelled"
    )
    assert timed_states.async_until(SLEEPER) is None

    timed_states.async_stop()


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
    timed_states = await _register(hass)

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
            timed_states.async_hold(SLEEPER, timedelta(milliseconds=1), STATE_OFF)
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

    assert timed_states.async_until(SLEEPER) is None, "it left a wake-up time behind"

    timed_states.async_stop()


async def test_turning_it_on_while_a_longer_snooze_saves_wins(
    hass: HomeAssistant,
) -> None:
    """Extending a snooze is the one moment the automation is off and watched.

    Turning it on there cancels the snooze, and the extension must not then
    turn it off again: that is an automation left off with nothing written
    down to wake it, which is the whole failure this exists to prevent.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    assert hass.states.get(SLEEPER).state == "off"

    saving = asyncio.Event()
    let_go = asyncio.Event()
    real_save = Store.async_save

    async def _held_open(self: Store, data: dict) -> None:
        saving.set()
        await let_go.wait()
        await real_save(self, data)

    with patch.object(Store, "async_save", _held_open):
        extending = hass.async_create_task(
            timed_states.async_hold(SLEEPER, AN_HOUR * 3, STATE_OFF)
        )

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
    assert timed_states.async_until(SLEEPER) is None, "and left a wake-up time behind"

    timed_states.async_stop()


async def test_a_wake_in_progress_stays_in_the_register(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """Because somebody else may write the register out while it is waking.

    A snooze for another automation saves the lot, and a record taken out
    early would not be in what got saved. Waking is marked rather than
    removed for exactly this.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    until = timed_states.async_until(SLEEPER)

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
        failing = hass.async_create_task(
            timed_states._async_restore(SLEEPER, _Held(until, STATE_OFF))
        )

        async with asyncio.timeout(5):
            await waking.wait()

        await timed_states.async_hold(OTHER, AN_HOUR, STATE_OFF)

        assert SLEEPER in hass_storage[STORAGE_KEY]["data"], (
            "somebody else's save wrote out a register without it"
        )

        let_go.set()

        async with asyncio.timeout(5):
            await failing

    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is not None

    timed_states.async_stop()


async def test_holding_again_during_a_restore_survives_it(
    hass: HomeAssistant,
) -> None:
    """Spook's own wake-up call is not somebody changing their mind.

    Asking for a fresh snooze while one is being woken leaves a new record,
    and the turning-on that follows must not be read as a person cancelling
    it. The mark on the entity is what tells those two apart.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    until = timed_states.async_until(SLEEPER)

    waking = asyncio.Event()
    let_go = asyncio.Event()
    real_turn_on = AutomationEntity.async_turn_on

    async def _held_open(self: AutomationEntity, **kwargs: object) -> None:
        waking.set()
        await let_go.wait()

        await real_turn_on(self, **kwargs)

    with patch.object(AutomationEntity, "async_turn_on", _held_open):
        woken = hass.async_create_task(
            timed_states._async_restore(SLEEPER, _Held(until, STATE_OFF))
        )

        async with asyncio.timeout(5):
            await waking.wait()

        # Somebody wants longer, while it is being woken.
        await timed_states.async_hold(SLEEPER, AN_HOUR * 3, STATE_OFF)
        asked_for = timed_states.async_until(SLEEPER)
        assert asked_for is not None

        let_go.set()

        async with asyncio.timeout(5):
            await woken

    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) == asked_for, (
        "the wake-up call was read as somebody cancelling the new snooze"
    )
    assert hass.states.get(SLEEPER).state == "off", (
        "the wake-up call left it running against the snooze that replaced it"
    )

    timed_states.async_stop()


async def test_an_automation_woken_once_can_still_be_woken_by_hand(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The mark on a waking automation has to come off again.

    Left on, it would go on excusing every turning-on as Spook's own for the
    rest of the run, and a person cancelling a later snooze would be ignored.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))
    assert hass.states.get(SLEEPER).state == "on"

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    await hass.services.async_call(
        "automation", "turn_on", {"entity_id": SLEEPER}, blocking=True
    )
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is None, (
        "it went on treating a person as itself"
    )

    timed_states.async_stop()


async def test_a_wake_that_finds_nothing_there_tries_again_later(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Entity services pass over what is unavailable and say nothing about it.

    So a wake-up call landing in the middle of a reload turns nothing on, and
    dropping the record there would leave the automation off for good. It
    keeps the record and has another go when the automation is back.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    # What a skipped entity looks like: the call comes back, nothing happened.
    async def _skipped(_self: AutomationEntity, **_kwargs: object) -> None:
        return

    with patch.object(AutomationEntity, "async_turn_on", _skipped):
        await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "off"
    assert timed_states.async_until(SLEEPER) is not None, (
        "it dropped the record for an automation it never woke"
    )

    # Away, and then back.
    hass.states.async_set(SLEEPER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    hass.states.async_set(SLEEPER, "off")
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", "it never had another go"
    assert timed_states.async_until(SLEEPER) is None

    timed_states.async_stop()


async def test_a_second_chance_queued_at_the_unload_does_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The second chance is handed to a task, which runs a moment later.

    Unloading in between has to leave that task with nothing to do, or an
    automation gets turned on by a register nobody is running.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    until = timed_states.async_until(SLEEPER)

    async def _skipped(_self: AutomationEntity, **_kwargs: object) -> None:
        return

    with patch.object(AutomationEntity, "async_turn_on", _skipped):
        await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert timed_states.async_until(SLEEPER) == until

    # Back again, which queues the second chance, and gone before it runs.
    hass.states.async_set(SLEEPER, STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    hass.states.async_set(SLEEPER, "off")
    timed_states.async_stop()

    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "off", (
        "it woke an automation after Spook was unloaded"
    )
    assert timed_states.async_until(SLEEPER) == until, "and forgot the snooze doing it"


async def test_one_that_is_away_is_left_alone_until_it_is_back(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Going unavailable is not the automation coming back.

    Trying to wake it there would be the same call failing the same way, and
    it is exactly the moment the state watch hears from most.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)

    async def _skipped(_self: AutomationEntity, **_kwargs: object) -> None:
        return

    with patch.object(AutomationEntity, "async_turn_on", _skipped):
        await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

        hass.states.async_set(SLEEPER, STATE_UNAVAILABLE)
        await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == STATE_UNAVAILABLE, (
        "it tried to wake one that was still away"
    )
    assert timed_states.async_until(SLEEPER) is not None

    timed_states.async_stop()


async def test_a_wake_cancelled_partway_keeps_the_record(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """A shutdown can cancel a wake mid-call, and it must leave no trace.

    Nothing is removed until the automation is actually on, so a cancellation
    lands on a register that still has the record, on disk as well as in
    memory. The next start sees to it.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    until = timed_states.async_until(SLEEPER)

    waking = asyncio.Event()

    async def _never_finishes(_self: AutomationEntity, **_kwargs: object) -> None:
        waking.set()
        await asyncio.Event().wait()

    with patch.object(AutomationEntity, "async_turn_on", _never_finishes):
        cancelled = hass.async_create_task(
            timed_states._async_restore(SLEEPER, _Held(until, STATE_OFF))
        )

        async with asyncio.timeout(5):
            await waking.wait()

        cancelled.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await cancelled

    assert timed_states.async_until(SLEEPER) == until, "the record went with the wake"
    assert SLEEPER in hass_storage[STORAGE_KEY]["data"]
    assert hass.states.get(SLEEPER).state == "off"

    timed_states.async_stop()


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
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    until = timed_states.async_until(SLEEPER)
    already_going = timed_states._async_due(SLEEPER, _Held(until, STATE_OFF))

    timed_states.async_stop()
    await already_going(dt_util.utcnow())
    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "off", (
        "it woke an automation after Spook was unloaded"
    )
    assert timed_states.async_until(SLEEPER) == until, (
        "and forgot the snooze on the way"
    )


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
        "data": {SLEEPER: _record(later)},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    hass.set_state(CoreState.running)
    timed_states = TimedStates(hass)

    saving = asyncio.Event()
    let_go = asyncio.Event()
    real_save = Store.async_save

    async def _held_open(self: Store, data: dict) -> None:
        saving.set()
        await let_go.wait()

        await real_save(self, data)

    with patch.object(Store, "async_save", _held_open):
        starting = hass.async_create_task(timed_states.async_start())

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

    assert timed_states.async_until(SLEEPER) is None, (
        "it kept counting down for one somebody had turned back on"
    )
    assert SLEEPER not in timed_states._timers, "and left its wake-up call armed"

    timed_states.async_stop()


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
        "data": {SLEEPER: _record(until), OTHER: _record(until)},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"), State(OTHER, "off")))
    await _automations(hass)

    hass.set_state(CoreState.running)
    timed_states = TimedStates(hass)

    waking = asyncio.Event()
    let_go = asyncio.Event()
    real_turn_on = AutomationEntity.async_turn_on

    async def _held_open(self: AutomationEntity, **kwargs: object) -> None:
        if self.entity_id == SLEEPER:
            waking.set()
            await let_go.wait()

        await real_turn_on(self, **kwargs)

    with patch.object(AutomationEntity, "async_turn_on", _held_open):
        starting = hass.async_create_task(timed_states.async_start())

        async with asyncio.timeout(5):
            await waking.wait()

        timed_states.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await starting

    await hass.async_block_till_done()

    assert hass.states.get(SLEEPER).state == "on", "the one it was on never woke"
    assert hass.states.get(OTHER).state == "off", (
        "it kept waking automations after Spook was unloaded"
    )
    assert timed_states.async_until(OTHER) is not None, "and forgot the one it skipped"


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
        "data": {SLEEPER: _record(until)},
    }
    await _automations(hass)

    hass.set_state(CoreState.not_running)
    timed_states = TimedStates(hass)

    reading = asyncio.Event()
    let_go = asyncio.Event()
    real_load = Store.async_load

    async def _held_open(self: Store) -> dict | None:
        reading.set()
        await let_go.wait()
        return await real_load(self)

    with patch.object(Store, "async_load", _held_open):
        starting = hass.async_create_task(timed_states.async_start())

        async with asyncio.timeout(5):
            await reading.wait()

        timed_states.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await starting

    assert timed_states._unsub_started is None, "it waited for a start after unloading"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert not timed_states._timers, "the start it waited for armed a timer"


async def test_unloading_while_a_snooze_is_saved_still_leaves_nothing_behind(
    hass: HomeAssistant,
) -> None:
    """The other side of the same thing: a call in flight when the entry goes.

    The automation is still turned off, because the snooze is written down by
    then and the next start picks it up. Only the waiting is dropped, there
    being nobody left to do it.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    saving = asyncio.Event()
    let_go = asyncio.Event()
    real_save = Store.async_save

    async def _held_open(self: Store, data: dict) -> None:
        saving.set()
        await let_go.wait()
        await real_save(self, data)

    with patch.object(Store, "async_save", _held_open):
        snoozed = hass.async_create_task(
            timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
        )

        async with asyncio.timeout(5):
            await saving.wait()

        timed_states.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await snoozed

    await hass.async_block_till_done()

    assert not timed_states._timers, "it armed a timer on a stopped register"
    assert timed_states._unsub_watching is None, "it left a listener behind"
    assert timed_states._unsub_registry is None, "it kept watching the registry"
    assert hass.states.get(SLEEPER).state == "off", "it did not turn it off at all"


async def test_it_holds_an_automation_on_and_puts_it_back_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The other direction, which is the same machinery mirrored.

    Everything the snooze tests pin applies here too, since there is one
    register doing both; what this checks is that the mirroring holds.
    """
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_ON)

    assert hass.states.get(SLEEPER).state == "on"
    assert timed_states.async_until(SLEEPER) is not None

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "off"
    assert timed_states.async_until(SLEEPER) is None

    timed_states.async_stop()


async def test_one_that_is_already_on_is_left_alone(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Turning it off later would be a change nobody asked for.

    The mirror of refusing to snooze one that is already off, and the reason
    both refusals exist: Spook only puts back what it moved itself.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    assert hass.states.get(SLEEPER).state == "on"

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_ON)

    assert timed_states.async_until(SLEEPER) is None
    assert "left automation.sleeper alone" in caplog.text

    timed_states.async_stop()


async def test_turning_one_off_by_hand_cancels_its_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Mirrored again: doing it yourself is the clearer statement."""
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_ON)

    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": SLEEPER}, blocking=True
    )
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is None, "it kept counting down"

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "off"

    timed_states.async_stop()


async def test_a_run_survives_a_restart(
    hass: HomeAssistant,
    hass_storage: dict,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An automation left on would stay on, which is the whole point again."""
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: _record(until, STATE_ON)},
    }
    await _automations(hass)
    assert hass.states.get(SLEEPER).state == "on"

    timed_states = await _register(hass)
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) == until

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(SLEEPER).state == "off", "it ran on past its time"

    timed_states.async_stop()


async def test_taking_over_the_old_store_writes_before_it_deletes(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """The old file goes only once the records are somewhere else.

    Taking over happens at setup, which is before Home Assistant has finished
    starting and therefore before anything else writes the records out. A
    delete first and a crash after would take every snooze with it.
    """
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[LEGACY_STORAGE_KEY] = {
        "version": 1,
        "data": {SLEEPER: until.isoformat()},
    }
    await _automations(hass)

    hass.set_state(CoreState.not_running)
    timed_states = TimedStates(hass)
    await timed_states.async_start()

    assert hass_storage[STORAGE_KEY]["data"] == {SLEEPER: _record(until)}, (
        "the old file was dropped before the records were written anywhere"
    )
    assert LEGACY_STORAGE_KEY not in hass_storage

    timed_states.async_stop()


async def test_records_written_before_the_other_direction_existed_still_read(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """The snooze-only store had its own name, and its records still count.

    A store migration only runs for the file being loaded, so nothing would
    have picked these up on its own: every snooze made before the upgrade
    would be dropped, and the automation left off for good.
    """
    until = dt_util.utcnow() + AN_HOUR
    hass_storage[LEGACY_STORAGE_KEY] = {
        "version": 1,
        "data": {SLEEPER: until.isoformat()},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)

    timed_states = await _register(hass)
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) == until

    assert hass_storage[STORAGE_KEY]["data"] == {SLEEPER: _record(until)}, (
        "it did not write the records out under the name it reads from"
    )
    assert LEGACY_STORAGE_KEY not in hass_storage, "it left the old file behind"

    # And it still means "off until then", not "on until then".
    await hass.services.async_call(
        "automation", "turn_on", {"entity_id": SLEEPER}, blocking=True
    )
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is None, (
        "turning it on did not read as cancelling, so the record came back wrong"
    )

    timed_states.async_stop()


async def test_a_renamed_automation_that_is_running_still_stops_on_time(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Renaming files the record under a name nobody uses any more.

    Invisible for a snooze, because a renamed automation comes back on by
    itself and that ends a snooze anyway. Not invisible here: one held on
    comes back on as well, which is the state it is being held in, so a
    record left behind means it runs forever.
    """
    mock_restore_cache(hass, (State(SLEEPER, "off"),))
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_ON)
    until = timed_states.async_until(SLEEPER)

    renamed = "automation.now_called_this"
    entity_registry.async_update_entity(SLEEPER, new_entity_id=renamed)
    await hass.async_block_till_done()

    assert timed_states.async_until(renamed) == until, "the record kept the old name"
    assert timed_states.async_until(SLEEPER) is None

    await _pass(hass, freezer, AN_HOUR + timedelta(minutes=1))

    assert hass.states.get(renamed).state == "off", "it ran on under its new name"

    timed_states.async_stop()


async def test_an_automation_removed_while_it_has_no_state_is_forgotten(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """A disabled automation has no state to go missing.

    So the state watch has nothing to hear, and the registry is the only place
    the removal shows up at all.
    """
    await _automations(hass)
    timed_states = await _register(hass)

    await timed_states.async_hold(SLEEPER, AN_HOUR, STATE_OFF)
    assert timed_states.async_until(SLEEPER) is not None

    entity_registry.async_update_entity(
        SLEEPER, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert hass.states.get(SLEEPER) is None
    assert timed_states.async_until(SLEEPER) is not None, "disabling is not deleting"

    entity_registry.async_remove(SLEEPER)
    await hass.async_block_till_done()

    assert timed_states.async_until(SLEEPER) is None, (
        "the record outlived the automation"
    )

    timed_states.async_stop()


async def test_unloading_partway_through_catching_up_touches_nothing_after(
    hass: HomeAssistant,
    hass_storage: dict,
) -> None:
    """The loop reads and drops records as it goes, and that has to stop too.

    Not just the putting-back: a register nobody is running must not be
    rewriting the store either, or a record it had not reached yet is lost.
    """
    overdue = dt_util.utcnow() - AN_HOUR
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION,
        "data": {SLEEPER: _record(overdue), OTHER: _record(overdue)},
    }
    mock_restore_cache(hass, (State(SLEEPER, "off"), State(OTHER, "on")))
    await _automations(hass)

    hass.set_state(CoreState.running)
    timed_states = TimedStates(hass)

    restoring = asyncio.Event()
    let_go = asyncio.Event()
    real_turn_on = AutomationEntity.async_turn_on

    async def _held_open(self: AutomationEntity, **kwargs: object) -> None:
        if self.entity_id == SLEEPER:
            restoring.set()
            await let_go.wait()

        await real_turn_on(self, **kwargs)

    with patch.object(AutomationEntity, "async_turn_on", _held_open):
        starting = hass.async_create_task(timed_states.async_start())

        async with asyncio.timeout(5):
            await restoring.wait()

        timed_states.async_stop()
        let_go.set()

        async with asyncio.timeout(5):
            await starting

    await hass.async_block_till_done()

    assert timed_states.async_until(OTHER) is not None, (
        "it dropped a record it had not reached before it was unloaded"
    )

    timed_states.async_stop()
