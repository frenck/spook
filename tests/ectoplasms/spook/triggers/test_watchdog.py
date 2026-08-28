"""Tests for the spook.watchdog trigger."""

# The watchdog's own state is what several of these are about, and there is no
# public way at it.
# ruff: noqa: SLF001
# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector, trigger as trigger_helper
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook import trigger_nesting
from custom_components.spook.ectoplasms.spook.triggers import (
    watchdog as watchdog_module,
)
from custom_components.spook.ectoplasms.spook.triggers.watchdog import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

DOOR = {"trigger": "state", "entity_id": "binary_sensor.door", "to": "on"}
MOTION = {"trigger": "state", "entity_id": "binary_sensor.motion", "to": "on"}
WITHIN = timedelta(minutes=2)

TWICE = 2


async def _automation(
    hass: HomeAssistant,
    options: dict[str, Any] | None = None,
) -> list[dict]:
    """Set up an automation on the trigger and record every bark."""
    barks: list[dict] = []

    async def _mark(call) -> None:  # noqa: ANN001
        barks.append(dict(call.data))

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "watching",
                    "trigger": {
                        "platform": "spook.watchdog",
                        "options": options
                        or {
                            "arm": [DOOR],
                            "expect": [MOTION],
                            "within": {"minutes": 2},
                        },
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {"armed_by": "{{ trigger.armed_by.entity_id }}"},
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    return barks


async def _detach(hass: HomeAssistant) -> None:
    """Turn the automation off, which detaches its triggers.

    The harness fails a test that leaves a timer or listener behind, and this
    trigger holds both, so this doubles as a check that it clears up.
    """
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "automation.watching"}, blocking=True
    )
    await hass.async_block_till_done()


async def _reset(hass: HomeAssistant) -> None:
    """Put the entities this uses in a known place."""
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()


async def _move(hass: HomeAssistant, entity_id: str, state: str) -> None:
    """Move an entity and let everything settle."""
    hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _wait_out(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the whole wait pass."""
    # `freezer.tick` moves the clock, so the time to fire at is simply the
    # time it now is. Adding the same stretch again, which reads as the
    # obvious thing, moves twice as far and sets off deadlines that should
    # still be pending.
    freezer.tick(WITHIN + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "watchdog" in await async_get_triggers(hass)


async def test_it_barks_when_nothing_follows(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The whole point: the door opened and nobody came in."""
    await _reset(hass)
    barks = await _automation(hass)

    await _move(hass, "binary_sensor.door", "on")
    assert not barks, "barked the moment it was armed"

    await _wait_out(hass, freezer)

    assert len(barks) == 1
    assert barks[0]["armed_by"] == "binary_sensor.door"

    await _detach(hass)


async def test_it_stays_quiet_when_the_expected_thing_arrives(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Which is the case it exists to tell apart from the other one."""
    await _reset(hass)
    barks = await _automation(hass)

    await _move(hass, "binary_sensor.door", "on")
    await _move(hass, "binary_sensor.motion", "on")
    await _wait_out(hass, freezer)

    assert not barks, "barked even though the expected thing arrived"

    await _detach(hass)


async def test_the_expected_thing_on_its_own_does_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Nothing is being waited for, so there is nothing to call off."""
    await _reset(hass)
    barks = await _automation(hass)

    await _move(hass, "binary_sensor.motion", "on")
    await _wait_out(hass, freezer)

    assert not barks

    await _detach(hass)


async def test_arming_again_starts_the_wait_over(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The wait is measured from the arming, so the latest one counts."""
    await _reset(hass)
    barks = await _automation(hass)

    await _move(hass, "binary_sensor.door", "on")

    # Most of the wait passes, and then it is armed again.
    freezer.tick(WITHIN - timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not barks

    await _move(hass, "binary_sensor.door", "off")
    await _move(hass, "binary_sensor.door", "on")

    # The old wait would have run out by now. The new one has not.
    freezer.tick(timedelta(seconds=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not barks, "the wait was not started over"

    await _wait_out(hass, freezer)
    assert len(barks) == 1

    await _detach(hass)


async def test_it_can_bark_more_than_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Barking is not the end of it: the next arming starts a new watch."""
    await _reset(hass)
    barks = await _automation(hass)

    for _ in range(TWICE):
        await _move(hass, "binary_sensor.door", "on")
        await _wait_out(hass, freezer)
        await _move(hass, "binary_sensor.door", "off")

    assert len(barks) == TWICE

    await _detach(hass)


async def test_it_takes_what_the_trigger_selector_produces(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The shape an automation built in the user interface actually has."""
    await _reset(hass)
    barks = await _automation(
        hass,
        {
            "arm": selector.TriggerSelector()(DOOR),
            "expect": selector.TriggerSelector()(MOTION),
            "within": {"minutes": 2},
        },
    )

    assert hass.states.get("automation.watching").state == "on", (
        "the automation did not load"
    )

    await _move(hass, "binary_sensor.door", "on")
    await _wait_out(hass, freezer)
    assert len(barks) == 1

    await _detach(hass)


async def test_a_deadline_only_ends_the_arming_it_was_set_for(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A due deadline waits for the lock like everything else.

    Arranged in order, because waiters on a lock are served in order: hold it,
    queue the re-arm, then let the first arming's deadline come due behind it.
    Barking then would be barking about a wait that was replaced.
    """
    await _reset(hass)
    validated = await SpookTrigger.async_validate_config(
        hass,
        {"options": {"arm": [DOOR], "expect": [MOTION], "within": {"minutes": 2}}},
    )
    options = validated["options"]
    barks: list[dict] = []

    watchdog = watchdog_module._Watchdog(
        hass,
        watchdog_module._Watch(
            arm=options["arm"], expect=options["expect"], within=options["within"]
        ),
        barks.append,
    )
    stop = await watchdog.async_start()

    try:
        await watchdog._async_armed({"trigger": {"entity_id": "a.b"}}, None)
        first = watchdog._armed
        assert first is not None

        await watchdog._lock.acquire()

        rearm = hass.async_create_task(
            watchdog._async_armed({"trigger": {"entity_id": "c.d"}}, None)
        )
        await asyncio.sleep(0)

        freezer.tick(WITHIN + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await asyncio.sleep(0)

        watchdog._lock.release()
        async with asyncio.timeout(5):
            await rearm
        await hass.async_block_till_done()

        assert not barks, "the replaced arming's deadline still barked"
        assert watchdog._armed is not None, "the new watch was called off"
        assert watchdog._armed is not first
    finally:
        stop()
        await hass.async_block_till_done()


async def test_stopping_while_attaching_leaves_nothing_behind(
    hass: HomeAssistant,
) -> None:
    """Stopping is synchronous and attaching is not.

    Overlapped on purpose. An earlier version of this test awaited
    `async_start` before stopping, which never puts the two at the same time
    and passed against a watchdog that leaked its listener. Review caught
    that, so this one holds the attach open and stops while it waits.
    """
    await _reset(hass)
    validated = await SpookTrigger.async_validate_config(
        hass,
        {"options": {"arm": [DOOR], "expect": [MOTION], "within": {"minutes": 2}}},
    )
    options = validated["options"]
    barks: list[dict] = []

    watchdog = watchdog_module._Watchdog(
        hass,
        watchdog_module._Watch(
            arm=options["arm"], expect=options["expect"], within=options["within"]
        ),
        barks.append,
    )

    real = trigger_helper.async_initialize_triggers
    hold = asyncio.Event()
    attaching = asyncio.Event()

    async def _suspending(*args: Any, **kwargs: Any):  # noqa: ANN202
        if "arming" in args[4]:
            attaching.set()
            await hold.wait()
        return await real(*args, **kwargs)

    with patch.object(
        trigger_nesting.trigger_helper,
        "async_initialize_triggers",
        _suspending,
    ):
        starting = hass.async_create_task(watchdog.async_start())
        async with asyncio.timeout(5):
            await attaching.wait()

        # The automation is turned off while the arming half is being
        # attached.
        watchdog.async_stop()

        hold.set()
        async with asyncio.timeout(5):
            await starting
        await hass.async_block_till_done()

    assert not watchdog._unsubs, "a listener was left behind"

    # And it really is deaf: arming it does nothing.
    await _move(hass, "binary_sensor.door", "on")
    assert watchdog._armed is None, "a stopped watchdog armed itself"

    watchdog.async_stop()
    await hass.async_block_till_done()


async def test_half_a_watchdog_is_refused(hass: HomeAssistant) -> None:
    """Without one half it either never starts or always barks."""
    await _reset(hass)
    validated = await SpookTrigger.async_validate_config(
        hass,
        {"options": {"arm": [DOOR], "expect": [MOTION], "within": {"minutes": 2}}},
    )
    options = validated["options"]

    watchdog = watchdog_module._Watchdog(
        hass,
        watchdog_module._Watch(
            arm=options["arm"], expect=options["expect"], within=options["within"]
        ),
        lambda _armed_by: None,
    )

    real = trigger_helper.async_initialize_triggers

    async def _expect_fails(*args: Any, **kwargs: Any):  # noqa: ANN202
        if "expected" in args[4]:
            return None
        return await real(*args, **kwargs)

    with (
        patch.object(
            watchdog_module.trigger_helper,
            "async_initialize_triggers",
            _expect_fails,
        ),
        pytest.raises(HomeAssistantError, match="expected triggers"),
    ):
        await watchdog.async_start()

    await hass.async_block_till_done()


async def test_a_zero_wait_is_refused(hass: HomeAssistant) -> None:
    """It would bark the moment it was armed."""
    with pytest.raises(vol.Invalid, match="no time to wait"):
        await SpookTrigger.async_validate_config(
            hass,
            {"options": {"arm": [DOOR], "expect": [MOTION], "within": {"seconds": 0}}},
        )


async def test_both_halves_are_required(hass: HomeAssistant) -> None:
    """A watchdog is two triggers and a duration, or it is not one."""
    for options in (
        {"expect": [MOTION], "within": {"minutes": 2}},
        {"arm": [DOOR], "within": {"minutes": 2}},
        {"arm": [DOOR], "expect": [MOTION]},
    ):
        with pytest.raises(vol.Invalid, match="required key"):
            await SpookTrigger.async_validate_config(hass, {"options": options})


async def test_barking_ends_the_watch(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Once it has barked there is nothing left to wait for.

    Checked on the watchdog itself, because what it costs to get this wrong is
    stale state rather than a wrong bark: the clock is gone either way, so the
    next arming works regardless. Pinning it keeps a later change from
    building on a watch that was supposed to be over.
    """
    await _reset(hass)
    validated = await SpookTrigger.async_validate_config(
        hass,
        {"options": {"arm": [DOOR], "expect": [MOTION], "within": {"minutes": 2}}},
    )
    options = validated["options"]
    barks: list[dict] = []

    watchdog = watchdog_module._Watchdog(
        hass,
        watchdog_module._Watch(
            arm=options["arm"], expect=options["expect"], within=options["within"]
        ),
        barks.append,
    )
    stop = await watchdog.async_start()

    try:
        await watchdog._async_armed({"trigger": {"entity_id": "a.b"}}, None)
        assert watchdog._armed is not None

        freezer.tick(WITHIN + timedelta(seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert len(barks) == 1
        assert watchdog._armed is None, "it is still waiting for something"
    finally:
        stop()
        await hass.async_block_till_done()


async def test_nothing_is_missed_while_the_halves_are_attaching(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Attaching suspends, so one half listens before the other does.

    Arming in that window would start a watch with nothing listening for what
    it waits for, and the thing arriving would be missed and barked about. So
    the expected half goes on first, and this drives both events through the
    window to say so.
    """
    await _reset(hass)
    validated = await SpookTrigger.async_validate_config(
        hass,
        {"options": {"arm": [DOOR], "expect": [MOTION], "within": {"minutes": 2}}},
    )
    options = validated["options"]
    barks: list[dict] = []

    watchdog = watchdog_module._Watchdog(
        hass,
        watchdog_module._Watch(
            arm=options["arm"], expect=options["expect"], within=options["within"]
        ),
        barks.append,
    )

    real = trigger_helper.async_initialize_triggers
    attached = 0

    async def _busy_window(*args: Any, **kwargs: Any):  # noqa: ANN202
        nonlocal attached
        unsub = await real(*args, **kwargs)
        attached += 1

        if attached == 1:
            # One half is listening and the other is not. Both halves of a
            # perfectly ordinary run happen right now.
            hass.states.async_set("binary_sensor.door", "on")
            hass.states.async_set("binary_sensor.motion", "on")
            await hass.async_block_till_done()

        return unsub

    with patch.object(
        trigger_nesting.trigger_helper, "async_initialize_triggers", _busy_window
    ):
        stop = await watchdog.async_start()

    try:
        await _wait_out(hass, freezer)
        assert not barks, "it barked about something it was not listening for"
    finally:
        stop()
        await hass.async_block_till_done()
