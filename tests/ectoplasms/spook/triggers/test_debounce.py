"""Tests for the spook.debounce trigger."""

# pylint: disable=protected-access,wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers import (
    debounce as debounce_module,
)
from custom_components.spook.ectoplasms.spook.triggers.debounce import SpookTrigger
from custom_components.spook.trigger import async_get_triggers
from tests.nested_trigger_helpers import async_stop_while_attaching

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

MOTION = {"trigger": "state", "entity_id": "binary_sensor.motion", "to": "on"}
DOOR = {"trigger": "state", "entity_id": "binary_sensor.door", "to": "on"}

HALF_A_MINUTE = timedelta(seconds=30)
THREE = 3
TWO = 2


async def _automation(
    hass: HomeAssistant,
    options: dict[str, Any] | None = None,
) -> list[dict]:
    """Set up an automation on the trigger and record every run."""
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
                    "alias": "settled",
                    "trigger": {
                        "platform": "spook.debounce",
                        "options": options or {"triggers": [MOTION], "for": "00:00:30"},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "count": "{{ trigger.count }}",
                                "span": "{{ trigger.span }}",
                                "entity_id": "{{ trigger.entity_id }}",
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
    trigger holds both, so this doubles as a check that it clears up.
    """
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "automation.settled"}, blocking=True
    )
    await hass.async_block_till_done()


async def _wait_out(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the quiet period pass with nothing happening in it."""
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _motion(hass: HomeAssistant) -> None:
    """Report motion once."""
    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "debounce" in await async_get_triggers(hass)


@pytest.mark.parametrize("pause", [{"seconds": 0}, "00:00:00", 0])
async def test_a_zero_pause_is_refused(hass: HomeAssistant, pause: object) -> None:
    """Zero collapses nothing: it is the trigger it was given, only slower."""
    with pytest.raises(vol.Invalid, match="longer than zero"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"triggers": [MOTION], "for": pause}}
        )


async def test_a_pause_is_required(hass: HomeAssistant) -> None:
    """Without one there is nothing to wait out."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"triggers": [MOTION]}}
        )


async def test_one_firing_is_reported_once_the_quiet_has_passed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Nothing is reported while it might still be a burst."""
    runs = await _automation(hass)

    await _motion(hass)
    assert runs == []

    await _wait_out(hass, freezer)

    assert len(runs) == 1
    assert runs[0]["count"] == 1
    assert runs[0]["entity_id"] == "binary_sensor.motion"

    await _detach(hass)


async def test_a_burst_arrives_as_one(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The point of the whole thing."""
    runs = await _automation(hass)

    await _motion(hass)
    freezer.tick(timedelta(seconds=5))
    await _motion(hass)
    freezer.tick(timedelta(seconds=5))
    await _motion(hass)
    assert runs == []

    await _wait_out(hass, freezer)

    assert len(runs) == 1
    assert runs[0]["count"] == THREE
    # From the first of the burst to the last, not counting the quiet after.
    assert runs[0]["span"] == "0:00:10"

    await _detach(hass)


async def test_every_firing_starts_the_wait_over(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A burst that keeps going is not reported at its first deadline.

    Twenty seconds in, motion again. The original deadline passes with nothing
    reported, because the quiet period restarted and has not run out yet.
    """
    runs = await _automation(hass)

    await _motion(hass)

    freezer.tick(timedelta(seconds=20))
    await _motion(hass)

    # Past the deadline the first firing would have had.
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert runs == []

    await _wait_out(hass, freezer)
    assert len(runs) == 1

    await _detach(hass)


async def test_two_bursts_are_two_reports(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Once reported, the next firing starts something new."""
    runs = await _automation(hass)

    await _motion(hass)
    await _wait_out(hass, freezer)
    assert len(runs) == 1

    await _motion(hass)
    await _wait_out(hass, freezer)

    assert len(runs) == TWO
    assert runs[1]["count"] == 1

    await _detach(hass)


async def test_several_triggers_are_collapsed_together(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Any of them keeps the burst going, and the lot arrives as one report."""
    runs = await _automation(hass, {"triggers": [MOTION, DOOR], "for": "00:00:30"})

    await _motion(hass)
    freezer.tick(timedelta(seconds=20))
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert runs == []

    await _wait_out(hass, freezer)

    assert len(runs) == 1
    # The last one to fire is the one at the top of the payload.
    assert runs[0]["entity_id"] == "binary_sensor.door"

    await _detach(hass)


async def test_the_payload_comes_from_the_last_firing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Including its context, so Spook's context conditions still work.

    Handing over a fresh context would make every settled burst read as
    nobody's doing, even when a person was behind the last of it.
    """
    fired: list[tuple[dict, Context | None]] = []

    config = await SpookTrigger.async_validate_config(
        hass, {"options": {"triggers": [MOTION], "for": "00:00:30"}}
    )
    trigger = SpookTrigger(
        hass, TriggerConfig(key="debounce", options=config["options"])
    )

    def _run(payload, _description, context=None) -> None:  # noqa: ANN001
        fired.append((payload, context))

    unsub = await trigger.async_attach_runner(_run)

    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=5))
    hass.states.async_set("binary_sensor.motion", "off")
    theirs = Context(user_id="abc123")
    hass.states.async_set("binary_sensor.motion", "on", context=theirs)
    await hass.async_block_till_done()

    await _wait_out(hass, freezer)
    unsub()

    assert len(fired) == 1
    payload, context = fired[0]
    assert context is theirs
    assert payload["to_state"].context is theirs
    assert payload["count"] == TWO
    assert payload["for"] == HALF_A_MINUTE


async def test_a_trigger_that_will_not_attach_refuses_the_lot(
    hass: HomeAssistant,
) -> None:
    """A trigger that is not listening cannot start the burst somebody asked about."""
    config = await SpookTrigger.async_validate_config(
        hass, {"options": {"triggers": [MOTION], "for": "00:00:30"}}
    )
    trigger = SpookTrigger(
        hass, TriggerConfig(key="debounce", options=config["options"])
    )

    def _run(_payload, _description, _context=None) -> None:  # noqa: ANN001
        """Never called."""

    with (
        patch(
            "custom_components.spook.ectoplasms.spook.triggers.debounce"
            ".async_attach_nested",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError, match="every trigger"),
    ):
        await trigger.async_attach_runner(_run)


async def test_stopping_while_attaching_leaves_nothing_behind(
    hass: HomeAssistant,
) -> None:
    """The same window every attach in Spook has."""
    config = await SpookTrigger.async_validate_config(
        hass, {"options": {"triggers": [MOTION, DOOR], "for": "00:00:30"}}
    )
    watcher = debounce_module._BurstWatcher(  # noqa: SLF001
        hass, config["options"]["triggers"], HALF_A_MINUTE, lambda *_args: None
    )

    await async_stop_while_attaching(hass, watcher, holding="trigger 2")

    assert not watcher._unsubs, "a listener was left behind"  # noqa: SLF001

    watcher.async_stop()


async def test_a_wait_left_over_from_a_gone_burst_reports_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The wait is tied to the burst that set it.

    Reached directly, because nothing in normal running can produce it: the
    pending wait is always dropped before a new one starts, and a cancelled
    timer cannot fire. It is a net under the case where a wait outlives the
    burst it belongs to, and a net nobody has pulled on is not a net.
    """
    reported: list[int] = []

    config = await SpookTrigger.async_validate_config(
        hass, {"options": {"triggers": [MOTION], "for": "00:00:30"}}
    )
    watcher = debounce_module._BurstWatcher(  # noqa: SLF001
        hass,
        config["options"]["triggers"],
        HALF_A_MINUTE,
        lambda count, *_args: reported.append(count),
    )
    stop = await watcher.async_start()

    await _motion(hass)
    assert watcher._burst is not None, "the firing started no burst"  # noqa: SLF001

    # The burst goes, its wait does not. That is the shape this guards.
    watcher._burst = None  # noqa: SLF001

    await _wait_out(hass, freezer)

    assert not reported

    stop()
