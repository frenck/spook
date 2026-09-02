"""Tests for the spook.sequence trigger."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector, trigger as trigger_helper
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers import (
    sequence as sequence_module,
)
from custom_components.spook.ectoplasms.spook.triggers.sequence import SpookTrigger
from custom_components.spook.trigger import async_get_triggers
from tests.nested_trigger_helpers import async_stop_while_attaching

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

DOOR = {"trigger": "state", "entity_id": "binary_sensor.door", "to": "on"}
MOTION = {"trigger": "state", "entity_id": "binary_sensor.motion", "to": "on"}
DISARMED = {"trigger": "state", "entity_id": "input_boolean.armed", "to": "off"}

TWICE = 2
THRICE = 3


async def _automation(
    hass: HomeAssistant,
    options: dict[str, Any] | None = None,
) -> list[dict]:
    """Set up an automation on the trigger and record every run's variables."""
    runs: list[dict] = []

    async def _mark(call) -> None:  # noqa: ANN001
        runs.append(dict(call.data))

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "in order",
                    "trigger": {
                        "platform": "spook.sequence",
                        "options": options or {"steps": [DOOR, MOTION]},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "steps": "{{ trigger.steps | count }}",
                                "first": "{{ trigger.steps[0].entity_id }}",
                                "last": "{{ trigger.steps[-1].entity_id }}",
                            },
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return runs


async def _detach(hass: HomeAssistant) -> None:
    """Turn the automation off, which detaches its trigger.

    The harness fails a test that leaves a timer or listener behind, and this
    trigger holds nested triggers and possibly a deadline, so this doubles as
    a check that it clears all of them up.
    """
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "automation.in_order"}, blocking=True
    )
    await hass.async_block_till_done()


async def _settle(hass: HomeAssistant) -> None:
    """Let the nested triggers finish attaching."""
    await hass.async_block_till_done()
    await hass.async_block_till_done()


async def _move(hass: HomeAssistant, entity_id: str, state: str, **kwargs) -> None:  # noqa: ANN003
    """Move an entity and let everything settle."""
    hass.states.async_set(entity_id, state, **kwargs)
    await _settle(hass)


async def _reset_entities(hass: HomeAssistant) -> None:
    """Put the entities this uses in a known place."""
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set("input_boolean.armed", "on")
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "sequence" in await async_get_triggers(hass)


async def test_it_fires_when_the_steps_happen_in_order(hass: HomeAssistant) -> None:
    """The whole point: door, then motion."""
    await _reset_entities(hass)
    runs = await _automation(hass)

    await _move(hass, "binary_sensor.door", "on")
    assert not runs, "fired on the first step alone"

    await _move(hass, "binary_sensor.motion", "on")

    assert len(runs) == 1
    assert runs[0]["steps"] == TWICE
    assert runs[0]["first"] == "binary_sensor.door"
    assert runs[0]["last"] == "binary_sensor.motion"

    await _detach(hass)


async def test_it_does_not_fire_out_of_order(hass: HomeAssistant) -> None:
    """Motion first is not this sequence, and nothing is listening for it."""
    await _reset_entities(hass)
    runs = await _automation(hass)

    await _move(hass, "binary_sensor.motion", "on")
    await _move(hass, "binary_sensor.door", "on")

    assert not runs, "fired on the steps in the wrong order"

    await _detach(hass)


async def test_the_same_step_twice_does_not_advance(hass: HomeAssistant) -> None:
    """A step is a step, not a counter."""
    await _reset_entities(hass)
    runs = await _automation(hass)

    await _move(hass, "binary_sensor.door", "on")
    await _move(hass, "binary_sensor.door", "off")
    await _move(hass, "binary_sensor.door", "on")

    assert not runs, "the first step firing twice completed the sequence"

    await _move(hass, "binary_sensor.motion", "on")
    assert len(runs) == 1

    await _detach(hass)


async def test_it_arms_itself_again_afterwards(hass: HomeAssistant) -> None:
    """Once round is not once ever."""
    await _reset_entities(hass)
    runs = await _automation(hass)

    for _ in range(TWICE):
        await _move(hass, "binary_sensor.door", "on")
        await _move(hass, "binary_sensor.motion", "on")
        await _move(hass, "binary_sensor.door", "off")
        await _move(hass, "binary_sensor.motion", "off")

    assert len(runs) == TWICE

    await _detach(hass)


async def test_a_timeout_abandons_the_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The deadline runs from the first step, and gives up when it passes."""
    await _reset_entities(hass)
    runs = await _automation(hass, {"steps": [DOOR, MOTION], "timeout": {"minutes": 2}})

    await _move(hass, "binary_sensor.door", "on")

    freezer.tick(timedelta(minutes=3))
    async_fire_time_changed(hass)
    await _settle(hass)

    await _move(hass, "binary_sensor.motion", "on")
    assert not runs, "the deadline passed and it still fired"

    # And it is back to waiting for the first step.
    await _move(hass, "binary_sensor.door", "off")
    await _move(hass, "binary_sensor.motion", "off")
    await _move(hass, "binary_sensor.door", "on")
    await _move(hass, "binary_sensor.motion", "on")
    assert len(runs) == 1, "it did not arm itself again after the timeout"

    await _detach(hass)


async def test_a_timeout_with_room_to_spare_still_fires(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A deadline is a limit, not a wait."""
    await _reset_entities(hass)
    runs = await _automation(hass, {"steps": [DOOR, MOTION], "timeout": {"minutes": 2}})

    await _move(hass, "binary_sensor.door", "on")
    freezer.tick(timedelta(seconds=30))
    await _move(hass, "binary_sensor.motion", "on")

    assert len(runs) == 1

    await _detach(hass)


async def test_a_reset_trigger_abandons_the_run(hass: HomeAssistant) -> None:
    """Something else happened that means the sequence no longer counts."""
    await _reset_entities(hass)
    runs = await _automation(hass, {"steps": [DOOR, MOTION], "reset": [DISARMED]})

    await _move(hass, "binary_sensor.door", "on")
    await _move(hass, "input_boolean.armed", "off")
    await _move(hass, "binary_sensor.motion", "on")

    assert not runs, "the reset did not abandon the run"

    await _detach(hass)


async def test_a_reset_while_nothing_runs_is_harmless(hass: HomeAssistant) -> None:
    """Resetting what has not started leaves the first step armed."""
    await _reset_entities(hass)
    runs = await _automation(hass, {"steps": [DOOR, MOTION], "reset": [DISARMED]})

    await _move(hass, "input_boolean.armed", "off")
    await _move(hass, "binary_sensor.door", "on")
    await _move(hass, "binary_sensor.motion", "on")

    assert len(runs) == 1, "a reset while idle broke the sequence"

    await _detach(hass)


async def test_it_carries_the_last_step_user_through(hass: HomeAssistant) -> None:
    """Whoever completed the sequence is who set the run going."""
    await _reset_entities(hass)
    user = await hass.auth.async_create_user("Ghost Hunter")

    ran: list[str] = []

    async def _mark(call) -> None:  # noqa: ANN001
        ran.append(call.data["which"])

    hass.services.async_register("test", "mark", _mark)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": which,
                    "trigger": {
                        "platform": "spook.sequence",
                        "options": {"steps": [DOOR, MOTION]},
                    },
                    "condition": [{"condition": f"spook.{which}"}],
                    "action": [{"action": "test.mark", "data": {"which": which}}],
                }
                for which in ("triggered_by_user", "not_triggered_by_user")
            ]
        },
    )
    await _settle(hass)

    await _move(hass, "binary_sensor.door", "on")
    await _move(hass, "binary_sensor.motion", "on", context=Context(user_id=user.id))

    assert ran == ["triggered_by_user"]

    for alias in ("triggered_by_user", "not_triggered_by_user"):
        await hass.services.async_call(
            "automation",
            "turn_off",
            {"entity_id": f"automation.{alias}"},
            blocking=True,
        )
    await hass.async_block_till_done()


async def test_it_takes_what_the_trigger_selector_produces(
    hass: HomeAssistant,
) -> None:
    """The shape an automation built in the user interface actually has.

    `TriggerSelector` validates with `cv.TRIGGER_SCHEMA`, which normalises to
    a list, the same trap the condition selector sets.
    """
    await _reset_entities(hass)
    runs = await _automation(
        hass, {"steps": selector.TriggerSelector()([DOOR, MOTION])}
    )

    assert hass.states.get("automation.in_order").state == "on", (
        "the automation did not load"
    )

    await _move(hass, "binary_sensor.door", "on")
    await _move(hass, "binary_sensor.motion", "on")
    assert len(runs) == 1

    await _detach(hass)


async def test_one_step_is_not_a_sequence(hass: HomeAssistant) -> None:
    """Refused, because there is no order to wait for."""
    with pytest.raises(vol.Invalid, match="at least 2 steps"):
        await SpookTrigger.async_validate_config(hass, {"options": {"steps": [DOOR]}})


async def test_steps_are_required(hass: HomeAssistant) -> None:
    """Without them there is nothing to wait for."""
    with pytest.raises(vol.Invalid, match="required key"):
        await SpookTrigger.async_validate_config(hass, {"options": {}})


async def test_a_bad_step_takes_down_only_its_own_automation(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A nested trigger that cannot be built is reported, not swallowed."""
    await _reset_entities(hass)

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "fine",
                    "trigger": {
                        "platform": "spook.sequence",
                        "options": {"steps": [DOOR, MOTION]},
                    },
                    "action": [],
                },
                {
                    "alias": "broken",
                    "trigger": {
                        "platform": "spook.sequence",
                        "options": {
                            "steps": [DOOR, {"trigger": "not_a_trigger"}],
                        },
                    },
                    "action": [],
                },
            ]
        },
    )
    await _settle(hass)

    assert hass.states.get("automation.fine").state == "on"
    assert hass.states.get("automation.broken").state == "unavailable"
    assert "not_a_trigger" in caplog.text

    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "automation.fine"}, blocking=True
    )
    await hass.async_block_till_done()


async def test_three_steps_all_have_to_land(hass: HomeAssistant) -> None:
    """Two is the minimum, not the maximum."""
    await _reset_entities(hass)
    hass.states.async_set("binary_sensor.window", "off")
    await hass.async_block_till_done()

    window = {"trigger": "state", "entity_id": "binary_sensor.window", "to": "on"}
    runs = await _automation(hass, {"steps": [DOOR, MOTION, window]})

    await _move(hass, "binary_sensor.door", "on")
    await _move(hass, "binary_sensor.motion", "on")
    assert not runs, "fired before the last step"

    await _move(hass, "binary_sensor.window", "on")
    assert len(runs) == 1
    assert runs[0]["steps"] == THRICE
    assert runs[0]["last"] == "binary_sensor.window"

    await _detach(hass)


async def test_a_step_firing_twice_in_one_go_does_not_run_ahead(
    hass: HomeAssistant,
) -> None:
    """Two of the same step arriving together must still be one step.

    Which Home Assistant mostly arranges by itself: it starts the action
    eagerly, so a step detaches itself while the first event is still being
    handed out and the second never reaches it. Measured. The test stays
    because that is an implementation detail of core's, and this is the
    behaviour that has to hold either way.
    """
    await _reset_entities(hass)
    runs = await _automation(hass)

    # No awaiting in between: both transitions to `on` are queued before the
    # trigger gets to handle either of them.
    hass.states.async_set("binary_sensor.door", "on")
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.door", "on")
    await _settle(hass)

    assert not runs, "the first step firing twice completed the sequence"

    await _move(hass, "binary_sensor.motion", "on")

    assert len(runs) == 1, "the second firing armed the last step twice"
    assert runs[0]["steps"] == TWICE, "the same step was collected twice"

    await _detach(hass)


async def test_a_reset_while_idle_leaves_the_first_step_alone(
    hass: HomeAssistant,
) -> None:
    """Nothing to abandon means nothing to touch.

    Counted rather than observed, because what re-arming for nothing costs is
    a gap: detaching and attaching again suspends, and a first step arriving
    in that window would be missed. Easier to pin the arming than to race it.
    """
    await _reset_entities(hass)

    arms = 0
    real = trigger_helper.async_initialize_triggers

    async def _counting(*args: Any, **kwargs: Any):  # noqa: ANN202
        nonlocal arms
        if args[4].startswith("step"):
            arms += 1
        return await real(*args, **kwargs)

    with patch.object(
        sequence_module.trigger_helper, "async_initialize_triggers", _counting
    ):
        await _automation(hass, {"steps": [DOOR, MOTION], "reset": [DISARMED]})
        armed_after_setup = arms

        await _move(hass, "input_boolean.armed", "off")
        await _move(hass, "input_boolean.armed", "on")
        await _move(hass, "input_boolean.armed", "off")

        assert arms == armed_after_setup, (
            f"a reset while idle re-armed the first step {arms - armed_after_setup} time(s)"
        )

    await _detach(hass)


async def test_a_step_answering_late_is_dropped(hass: HomeAssistant) -> None:
    """A step that queued behind a reset must not be taken when it gets in.

    Driven straight rather than through the event bus. The interleaving that
    reaches this is a reset or a deadline holding the lock while a step waits
    behind it, and forcing that through real events is a race, so the sequence
    is walked by hand instead.
    """
    validated = await SpookTrigger.async_validate_config(
        hass, {"options": {"steps": [DOOR, MOTION]}}
    )
    steps = validated["options"]["steps"]
    completed: list[list[dict]] = []

    watcher = sequence_module._SequenceWatcher(  # noqa: SLF001
        hass,
        sequence_module._Sequence(steps=steps, reset=[], timeout=None),  # noqa: SLF001
        lambda collected, _duration, _context: completed.append(collected),
    )
    stop = await watcher.async_start()

    try:
        # The first step lands, so the second is armed.
        await watcher._async_step_fired(0, {"trigger": {"entity_id": "a.b"}}, None)  # noqa: SLF001
        assert not completed

        # The first step answers again, late. It is no longer the step being
        # waited for, so it counts for nothing.
        await watcher._async_step_fired(0, {"trigger": {"entity_id": "a.b"}}, None)  # noqa: SLF001
        assert not completed, "a late first step completed a two step sequence"

        # And the run is still waiting for the second step, not a third one.
        await watcher._async_step_fired(1, {"trigger": {"entity_id": "c.d"}}, None)  # noqa: SLF001
        assert len(completed) == 1
        assert len(completed[0]) == TWICE, "the late step was collected"
    finally:
        stop()
        await hass.async_block_till_done()


async def test_stopping_while_re_arming_leaves_nothing_behind(
    hass: HomeAssistant,
) -> None:
    """Turning the automation off mid-flight must not leak a listener.

    Stopping is synchronous, arming is not. Reproduced before it was fixed: a
    watcher belonging to an automation that had been turned off went on
    completing sequences, because the arm that was suspended when it stopped
    stored its handle afterwards and nobody was left to call it.
    """
    await _reset_entities(hass)
    validated = await SpookTrigger.async_validate_config(
        hass, {"options": {"steps": [DOOR, MOTION]}}
    )
    completed: list[list[dict]] = []

    watcher = sequence_module._SequenceWatcher(  # noqa: SLF001
        hass,
        sequence_module._Sequence(  # noqa: SLF001
            steps=validated["options"]["steps"], reset=[], timeout=None
        ),
        lambda collected, _duration, _context: completed.append(collected),
    )
    stop = await watcher.async_start()

    real = trigger_helper.async_initialize_triggers
    hold = asyncio.Event()
    arming = asyncio.Event()

    async def _suspending(*args: Any, **kwargs: Any):  # noqa: ANN202
        if args[4].startswith("step 2"):
            arming.set()
            await hold.wait()
        return await real(*args, **kwargs)

    with patch.object(
        sequence_module.trigger_helper,
        "async_initialize_triggers",
        _suspending,
    ):
        landing = hass.async_create_task(
            watcher._async_step_fired(0, {"trigger": {}}, None)  # noqa: SLF001
        )
        async with asyncio.timeout(5):
            await arming.wait()

        # The automation is turned off while arming the second step waits.
        stop()

        hold.set()
        async with asyncio.timeout(5):
            await landing
        await hass.async_block_till_done()

    assert watcher._run.unsub_step is None, "a listener was left behind"  # noqa: SLF001

    # And it really is deaf: the second step arriving does nothing.
    await _move(hass, "binary_sensor.motion", "on")
    assert not completed, "a stopped watcher completed a sequence"


async def test_the_duration_ends_when_the_last_step_lands(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Not when it has finished listening again.

    Arming the first step again suspends, so reading the clock after it would
    fold however long that took into what the sequence is reported to have
    taken.
    """
    await _reset_entities(hass)
    reported: list[timedelta] = []

    validated = await SpookTrigger.async_validate_config(
        hass, {"options": {"steps": [DOOR, MOTION]}}
    )

    watcher = sequence_module._SequenceWatcher(  # noqa: SLF001
        hass,
        sequence_module._Sequence(  # noqa: SLF001
            steps=validated["options"]["steps"], reset=[], timeout=None
        ),
        lambda _collected, duration, _context: reported.append(duration),
    )
    stop = await watcher.async_start()

    try:
        await watcher._async_step_fired(0, {"trigger": {}}, None)  # noqa: SLF001
        freezer.tick(timedelta(seconds=5))

        real = trigger_helper.async_initialize_triggers

        async def _slow_re_arm(*args: Any, **kwargs: Any):  # noqa: ANN202
            if args[4].startswith("step 1"):
                # Time passes while listening starts again.
                freezer.tick(timedelta(minutes=10))
            return await real(*args, **kwargs)

        with patch.object(
            sequence_module.trigger_helper,
            "async_initialize_triggers",
            _slow_re_arm,
        ):
            await watcher._async_step_fired(1, {"trigger": {}}, None)  # noqa: SLF001
    finally:
        stop()
        await hass.async_block_till_done()

    assert len(reported) == 1
    assert reported[0] == timedelta(seconds=5), (
        f"reported {reported[0]}, so re-arming was counted as part of the run"
    )


async def test_a_reset_that_cannot_attach_is_reported(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A sequence that quietly stops being interruptible is worth a line.

    The steps still attach, so the trigger works and reports itself as fine.
    Only the reset is missing, and nothing else would say so.
    """
    await _reset_entities(hass)
    validated = await SpookTrigger.async_validate_config(
        hass, {"options": {"steps": [DOOR, MOTION], "reset": [DISARMED]}}
    )

    watcher = sequence_module._SequenceWatcher(  # noqa: SLF001
        hass,
        sequence_module._Sequence(  # noqa: SLF001
            steps=validated["options"]["steps"],
            reset=validated["options"]["reset"],
            timeout=None,
        ),
        lambda *_args: None,
    )

    real = trigger_helper.async_initialize_triggers

    async def _reset_fails(*args: Any, **kwargs: Any):  # noqa: ANN202
        if args[4].startswith("the reset triggers"):
            return None
        return await real(*args, **kwargs)

    with patch.object(
        sequence_module.trigger_helper, "async_initialize_triggers", _reset_fails
    ):
        stop = await watcher.async_start()

    stop()
    await hass.async_block_till_done()

    assert "could not attach the reset triggers" in caplog.text
    assert "nothing will abandon a run under way" in caplog.text, (
        "the line says a healthy sequence will not fire"
    )


async def test_a_deadline_only_ends_the_run_it_was_set_for(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A due deadline waits for the lock like everything else.

    Built deliberately, because the interleaving is narrow and only the narrow
    version shows anything. A deadline abandoning a run that has not started
    yet leaves exactly what it found, so what has to be arranged is a deadline
    from a finished run arriving after the next one has already got somewhere.

    Waiters on a lock are served in order, so holding it and queueing three
    things behind it puts them in that order every time: the step that
    completes the first run, the first step of the second, and then the stale
    deadline.
    """
    await _reset_entities(hass)
    validated = await SpookTrigger.async_validate_config(
        hass,
        {"options": {"steps": [DOOR, MOTION], "timeout": {"seconds": 30}}},
    )
    completed: list[list[dict]] = []

    watcher = sequence_module._SequenceWatcher(  # noqa: SLF001
        hass,
        sequence_module._Sequence(  # noqa: SLF001
            steps=validated["options"]["steps"],
            reset=[],
            timeout=validated["options"]["timeout"],
        ),
        lambda collected, _duration, _context: completed.append(collected),
    )
    stop = await watcher.async_start()

    try:
        # A run starts, so a deadline is set for it.
        await watcher._async_step_fired(0, {"trigger": {}}, None)  # noqa: SLF001
        assert watcher._run.unsub_timeout is not None  # noqa: SLF001

        await watcher._lock.acquire()  # noqa: SLF001

        # The last step of that run lands, and waits for the lock.
        landing = hass.async_create_task(
            watcher._async_step_fired(1, {"trigger": {}}, None)  # noqa: SLF001
        )
        await asyncio.sleep(0)

        # So does the first step of the run after it.
        next_run = hass.async_create_task(
            watcher._async_step_fired(0, {"trigger": {}}, None)  # noqa: SLF001
        )
        await asyncio.sleep(0)

        # And only then does the first run's deadline come due, joining the
        # back of the queue.
        freezer.tick(timedelta(seconds=31))
        async_fire_time_changed(hass)
        await asyncio.sleep(0)

        watcher._lock.release()  # noqa: SLF001
        async with asyncio.timeout(5):
            await landing
            await next_run
        await hass.async_block_till_done()

        assert len(completed) == 1, "the first run did not complete"
        assert watcher._run.armed == 1, (  # noqa: SLF001
            "a finished run's deadline abandoned the run that followed it"
        )
        assert len(watcher._run.collected) == 1  # noqa: SLF001
    finally:
        stop()
        await hass.async_block_till_done()


async def test_a_first_step_that_cannot_attach_is_refused(
    hass: HomeAssistant,
) -> None:
    """An automation that can never fire must not look healthy.

    Refusing is what gets Home Assistant to mark it unavailable. A line in the
    log alone would leave it enabled, silent, and indistinguishable from one
    that is simply waiting.
    """
    await _reset_entities(hass)
    validated = await SpookTrigger.async_validate_config(
        hass, {"options": {"steps": [DOOR, MOTION], "reset": [DISARMED]}}
    )

    watcher = sequence_module._SequenceWatcher(  # noqa: SLF001
        hass,
        sequence_module._Sequence(  # noqa: SLF001
            steps=validated["options"]["steps"],
            reset=validated["options"]["reset"],
            timeout=None,
        ),
        lambda *_args: None,
    )

    real = trigger_helper.async_initialize_triggers

    async def _steps_fail(*args: Any, **kwargs: Any):  # noqa: ANN202
        if args[4].startswith("step"):
            return None
        return await real(*args, **kwargs)

    with (
        patch.object(
            sequence_module.trigger_helper, "async_initialize_triggers", _steps_fail
        ),
        pytest.raises(HomeAssistantError, match="first step"),
    ):
        await watcher.async_start()

    # And it took the reset triggers back down on its way out, because nobody
    # was handed a way to do it.
    assert watcher._unsub_reset is None, "the reset triggers were left attached"  # noqa: SLF001
    await hass.async_block_till_done()


async def test_stopping_while_attaching_the_reset_leaves_nothing_behind(
    hass: HomeAssistant,
) -> None:
    """The third attach in this codebase with the same window.

    Two of them were found by review, one after the other, so this one is
    covered by the same shape of test rather than waiting to be the third.
    """
    await _reset_entities(hass)
    validated = await SpookTrigger.async_validate_config(
        hass, {"options": {"steps": [DOOR, MOTION], "reset": [DISARMED]}}
    )

    watcher = sequence_module._SequenceWatcher(  # noqa: SLF001
        hass,
        sequence_module._Sequence(  # noqa: SLF001
            steps=validated["options"]["steps"],
            reset=validated["options"]["reset"],
            timeout=None,
        ),
        lambda *_args: None,
    )

    await async_stop_while_attaching(hass, watcher, holding="reset")

    assert watcher._unsub_reset is None, "a reset listener was left behind"  # noqa: SLF001
    assert watcher._run.unsub_step is None, "a step listener was left behind"  # noqa: SLF001

    watcher.async_stop()
    await hass.async_block_till_done()


async def test_a_sequence_with_no_time_to_finish_is_refused(
    hass: HomeAssistant,
) -> None:
    """It would run out the moment it starts, never getting past step one.

    `positive_time_period` counts zero as positive, and the sibling triggers
    that take a duration already say no to it.
    """
    with pytest.raises(vol.Invalid, match="no time to finish"):
        await SpookTrigger.async_validate_config(
            hass,
            {"options": {"steps": [DOOR, MOTION], "timeout": {"seconds": 0}}},
        )
