"""Tests for snoozing automations."""

# The register's own bookkeeping is what one of these is about, and there is no
# public way at it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from homeassistant.components.automation import AutomationEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE
from homeassistant.core import Context, CoreState, State
from homeassistant.exceptions import HomeAssistantError
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

    from homeassistant.core import HomeAssistant

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

    A reload only makes an automation unavailable for a moment, which is why
    this waits for the state to be gone for good rather than merely away.
    """
    await _automations(hass)
    snoozing = await _register(hass)

    await snoozing.async_snooze(SLEEPER, AN_HOUR)
    assert snoozing.async_until(SLEEPER) is not None

    entity_registry.async_remove(SLEEPER)
    await hass.async_block_till_done()

    assert snoozing.async_until(SLEEPER) is None, "the snooze outlived its automation"

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
