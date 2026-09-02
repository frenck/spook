"""Tests for the spook.recovered trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CoreState
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.recovered import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

QUARTER_OF_AN_HOUR = timedelta(minutes=15)


async def _automation(
    hass: HomeAssistant,
    target: dict,
    duration: str = "00:15:00",
) -> list[dict]:
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
                    "alias": "came back",
                    "trigger": {
                        "platform": "spook.recovered",
                        "target": target,
                        "options": {"for": duration},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "entity_id": "{{ trigger.entity_id }}",
                                "gone_for": "{{ trigger.gone_for }}",
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
    """Turn the automation off, which detaches its trigger.

    The harness fails a test that leaves a timer or listener behind, so this
    doubles as a check that the trigger clears up after itself.
    """
    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.came_back"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "recovered" in await async_get_triggers(hass)


async def test_a_target_is_required(hass: HomeAssistant) -> None:
    """Without a target there is nothing to watch."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"for": {"minutes": 15}}}
        )


@pytest.mark.parametrize("duration", [{"minutes": 0}, "00:00:00", 0])
async def test_a_zero_duration_is_refused(
    hass: HomeAssistant, duration: object
) -> None:
    """Zero would fire on every flicker, which is what this exists to filter."""
    with pytest.raises(vol.Invalid, match="longer than zero"):
        await SpookTrigger.async_validate_config(
            hass,
            {"target": {"entity_id": "sensor.probe"}, "options": {"for": duration}},
        )


@pytest.mark.parametrize("target", [{}, {"entity_id": []}, {"area_id": None}])
async def test_a_target_that_names_nothing_is_refused(
    hass: HomeAssistant,
    target: dict,
) -> None:
    """An empty target would load and then watch nothing at all."""
    with pytest.raises(vol.Invalid, match="must name at least one"):
        await SpookTrigger.async_validate_config(
            hass, {"target": target, "options": {"for": {"minutes": 15}}}
        )


async def test_a_long_absence_fires_when_it_ends(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The point of the whole thing."""
    hass.states.async_set("sensor.probe", "21.5")
    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    freezer.tick(timedelta(hours=1))
    hass.states.async_set("sensor.probe", "21.7")
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["entity_id"] == "sensor.probe"
    assert ran[0]["gone_for"] == "1:00:00"

    await _detach(hass)


async def test_a_flicker_is_not_a_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Reloading an integration takes its entities away and back in a second.

    Without the duration doing its job, every reload in the house would read
    as everything in it recovering.
    """
    hass.states.async_set("sensor.probe", "21.5")
    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=2))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    assert ran == []

    await _detach(hass)


async def test_unknown_on_the_way_back_does_not_end_the_absence(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A device that reconnects before it has a reading is not back yet.

    It also must not restart the clock: the absence began when the entity
    went unavailable, and it is still going.
    """
    hass.states.async_set("sensor.probe", "21.5")
    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=20))
    hass.states.async_set("sensor.probe", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert ran == []

    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.probe", "21.7")
    await hass.async_block_till_done()

    assert len(ran) == 1
    # Twenty-one minutes, counted from when it went, not from the unknown.
    assert ran[0]["gone_for"] == "0:21:00"

    await _detach(hass)


async def test_a_first_reading_is_not_a_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An entity that sits at unknown and then gets a value never went away.

    Plenty of entities are unknown for hours after a restart because nothing
    has reported yet. Treating unknown as gone would fire for every one of
    them the moment it works.
    """
    hass.states.async_set("sensor.probe", STATE_UNKNOWN)
    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    freezer.tick(timedelta(hours=2))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    assert ran == []

    await _detach(hass)


async def test_an_absence_that_started_before_anybody_watched_still_counts(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An automation reloaded while the device was down still reports the truth.

    The entity carries the moment it went in `last_changed`, so the answer is
    how long the device was away and not how long Spook has been looking.
    """
    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    freezer.tick(timedelta(hours=3))

    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["gone_for"] == "3:00:00"

    await _detach(hass)


async def test_a_slow_start_is_not_a_house_full_of_recoveries(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Nothing is recorded until Home Assistant is up.

    An integration that sets up minutes into a start brings every one of its
    entities from unavailable to a value at that moment. Recorded through the
    start, each of those would be a recovery timed from whenever the entity
    happened to be created.
    """
    hass.set_state(CoreState.starting)
    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    freezer.tick(timedelta(minutes=30))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    assert ran == []

    # Once the house is up, the next absence is watched as normal.
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=20))
    hass.states.async_set("sensor.probe", "21.7")
    await hass.async_block_till_done()

    assert len(ran) == 1

    await _detach(hass)


async def test_an_entity_removed_while_away_does_not_report_on_return(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A new entity that happens to reuse the name has recovered from nothing."""
    hass.states.async_set("sensor.probe", "21.5")
    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    freezer.tick(timedelta(hours=1))
    hass.states.async_remove("sensor.probe")
    await hass.async_block_till_done()

    hass.states.async_set("sensor.probe", "21.7")
    await hass.async_block_till_done()

    assert ran == []

    await _detach(hass)


async def test_the_payload_carries_when_it_went_and_for_how_long(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """`gone_since` is handed over in local time, like every Spook trigger.

    Attached straight rather than through an automation, because this is
    about what the trigger hands over and not about what an action makes of
    it. It also covers the entity being away before the trigger existed.
    """
    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    went = hass.states.get("sensor.probe").last_changed

    fired: list[dict] = []
    trigger = SpookTrigger(
        hass,
        TriggerConfig(
            key="recovered",
            target={"entity_id": "sensor.probe"},
            options={"for": QUARTER_OF_AN_HOUR},
        ),
    )

    def _run(payload, _description, _context=None) -> None:  # noqa: ANN001
        fired.append(payload)

    unsub = await trigger.async_attach_runner(_run)

    freezer.tick(timedelta(minutes=20))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    unsub()

    assert len(fired) == 1
    assert fired[0]["entity_id"] == "sensor.probe"
    assert fired[0]["gone_since"] == dt_util.as_local(went)
    assert fired[0]["gone_for"] == timedelta(minutes=20)
    assert fired[0]["for"] == QUARTER_OF_AN_HOUR


async def test_flipping_back_out_does_not_restart_the_clock(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A device thrashing on the way back is one absence, not several.

    It goes unavailable, comes far enough to say unknown, drops out again,
    and finally reports. The absence began at the first of those and has not
    ended since.
    """
    hass.states.async_set("sensor.probe", "21.5")
    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=10))
    hass.states.async_set("sensor.probe", STATE_UNKNOWN)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("sensor.probe", STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=10))
    hass.states.async_set("sensor.probe", "21.7")
    await hass.async_block_till_done()

    assert len(ran) == 1
    # Twenty-one minutes in total, not the ten since the last drop-out.
    assert ran[0]["gone_for"] == "0:21:00"

    await _detach(hass)


async def test_a_spell_of_unknown_is_not_an_absence(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An entity that reports unknown for an hour never went away.

    Unknown is the entity answering: it is reachable and has no value. That
    is a different complaint from being gone, and `spook.stale` is the one
    that covers a sensor holding nothing useful. Only unavailable starts an
    absence here.
    """
    hass.states.async_set("sensor.probe", "21.5")
    ran = await _automation(hass, {"entity_id": "sensor.probe"})

    hass.states.async_set("sensor.probe", STATE_UNKNOWN)
    await hass.async_block_till_done()

    freezer.tick(timedelta(hours=1))
    hass.states.async_set("sensor.probe", "21.7")
    await hass.async_block_till_done()

    assert ran == []

    await _detach(hass)
