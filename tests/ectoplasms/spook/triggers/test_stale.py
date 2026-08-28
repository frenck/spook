"""Tests for the spook.stale trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.stale import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

AN_HOUR = timedelta(hours=1)


async def _automation(hass: HomeAssistant, target: dict, duration: str) -> list[dict]:
    """Set up an automation on the stale trigger and record every run."""
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
                    "alias": "gone quiet",
                    "trigger": {
                        "platform": "spook.stale",
                        "target": target,
                        "options": {"for": duration},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "entity_id": "{{ trigger.entity_id }}",
                                "last_reported": "{{ trigger.last_reported }}",
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
        {"entity_id": "automation.gone_quiet"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "stale" in await async_get_triggers(hass)


async def test_a_target_is_required(hass: HomeAssistant) -> None:
    """Without a target there is nothing to watch."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"for": {"hours": 1}}}
        )


async def test_a_duration_is_required(hass: HomeAssistant) -> None:
    """Without a duration there is no telling when silence counts."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass, {"target": {"entity_id": "sensor.probe"}, "options": {}}
        )


@pytest.mark.parametrize("duration", [{"hours": 0}, "00:00:00", 0])
async def test_a_zero_duration_is_refused(
    hass: HomeAssistant, duration: object
) -> None:
    """Zero would put the deadline in the past, so it would never fire at all.

    Better refused at load than loading and quietly doing nothing.
    """
    with pytest.raises(vol.Invalid, match="longer than zero"):
        await SpookTrigger.async_validate_config(
            hass,
            {"target": {"entity_id": "sensor.probe"}, "options": {"for": duration}},
        )


async def test_it_fires_once_an_entity_falls_silent(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Nothing writes to the entity for the whole duration, so it fires."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    ran = await _automation(hass, {"entity_id": "sensor.probe"}, "01:00:00")

    freezer.tick(timedelta(minutes=59))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not ran

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["entity_id"] == "sensor.probe"

    await _detach(hass)


async def test_the_same_value_reported_again_keeps_it_alive(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An entity repeating itself is alive, and this is the whole point.

    A sensor that keeps publishing 21.5 every minute has not gone anywhere.
    Watching `last_reported` rather than `last_changed` is what tells the two
    apart, so this is the test that pins the trigger's meaning.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    ran = await _automation(hass, {"entity_id": "sensor.probe"}, "01:00:00")

    # Well past the hour, but reporting the same value all the way through.
    for _ in range(4):
        freezer.tick(timedelta(minutes=30))
        hass.states.async_set("sensor.probe", "21.5")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert not ran, "fired for an entity that never stopped reporting"

    await _detach(hass)


async def test_it_still_fires_after_a_run_of_identical_reports(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The real shape of a dying sensor: repeats itself for hours, then stops.

    This is the test that separates `last_reported` from `last_changed`. Keyed
    on `last_changed`, the deadline stays pinned to the one time the value
    moved, slides into the past, and the entity is never watched again: it
    could die and nothing would ever say so.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    ran = await _automation(hass, {"entity_id": "sensor.probe"}, "01:00:00")

    # Three hours of loyally repeating the same reading.
    for _ in range(6):
        freezer.tick(timedelta(minutes=30))
        hass.states.async_set("sensor.probe", "21.5")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert not ran

    # And then it stops.
    freezer.tick(AN_HOUR + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1, "a sensor that repeated itself then died went unnoticed"
    assert ran[0]["entity_id"] == "sensor.probe"

    await _detach(hass)


async def test_it_reports_when_the_entity_last_spoke(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """`trigger.last_reported` is when it went quiet, not when we noticed."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    ran = await _automation(hass, {"entity_id": "sensor.probe"}, "01:00:00")

    # Overshoot the deadline by a long way, the way a busy system would.
    freezer.tick(timedelta(hours=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(ran) == 1
    assert ran[0]["last_reported"].startswith("2026-08-27 12:00:00")

    await _detach(hass)


async def test_it_watches_everything_in_an_area(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """A target can name an area, and every entity in it is watched."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))

    area = area_registry.async_create("Attic")
    entry = entity_registry.async_get_or_create("sensor", "demo", "attic-probe")
    entity_registry.async_update_entity(entry.entity_id, area_id=area.id)

    hass.states.async_set(entry.entity_id, "21.5")
    hass.states.async_set("sensor.elsewhere", "21.5")
    await hass.async_block_till_done()

    ran = await _automation(hass, {"area_id": area.id}, "01:00:00")

    freezer.tick(AN_HOUR + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [run["entity_id"] for run in ran] == [entry.entity_id]

    await _detach(hass)


async def test_a_changing_value_keeps_it_alive(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A value that keeps moving resets the clock too.

    Obvious, and the counterpart to the identical-report case: a write that
    changes the state and a write that does not are two different events in
    Home Assistant, and only both of them add up to "something wrote here".
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    ran = await _automation(hass, {"entity_id": "sensor.probe"}, "01:00:00")

    for step in range(4):
        freezer.tick(timedelta(minutes=30))
        hass.states.async_set("sensor.probe", f"{21.5 + step}")
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert not ran, "fired for an entity whose value kept moving"

    await _detach(hass)


async def test_an_entity_joining_the_target_is_picked_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """Move an entity into the watched area and it starts being watched.

    The re-aiming comes from core's target tracker, but keeping the timers and
    the write listeners in step with the new set is this trigger's job.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))

    area = area_registry.async_create("Attic")
    entry = entity_registry.async_get_or_create("sensor", "demo", "late-joiner")
    hass.states.async_set(entry.entity_id, "21.5")
    await hass.async_block_till_done()

    ran = await _automation(hass, {"area_id": area.id}, "01:00:00")

    # Nothing in the area yet, so nothing is being watched.
    freezer.tick(AN_HOUR + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert not ran

    # Now it joins, and reports once so it starts out alive.
    entity_registry.async_update_entity(entry.entity_id, area_id=area.id)
    hass.states.async_set(entry.entity_id, "21.5")
    await hass.async_block_till_done()

    freezer.tick(AN_HOUR + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [run["entity_id"] for run in ran] == [entry.entity_id]

    await _detach(hass)


async def test_an_entity_leaving_the_target_stops_being_watched(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """Take an entity out of the watched area and its pending wait goes too.

    Without dropping it, the wait outlives the target and the automation runs
    for something it no longer covers.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))

    area = area_registry.async_create("Attic")
    entry = entity_registry.async_get_or_create("sensor", "demo", "leaver")
    entity_registry.async_update_entity(entry.entity_id, area_id=area.id)

    hass.states.async_set(entry.entity_id, "21.5")
    await hass.async_block_till_done()

    ran = await _automation(hass, {"area_id": area.id}, "01:00:00")

    # Out of the area, halfway through the hour.
    freezer.tick(timedelta(minutes=30))
    entity_registry.async_update_entity(entry.entity_id, area_id=None)
    await hass.async_block_till_done()

    freezer.tick(AN_HOUR)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not ran, "fired for an entity that had left the target"

    await _detach(hass)


async def test_a_target_entity_without_a_state_is_skipped(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry,  # noqa: ANN001
) -> None:
    """A registry entry with no state yet has nothing to be silent about."""
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))

    entry = entity_registry.async_get_or_create("sensor", "demo", "stateless")

    ran = await _automation(hass, {"entity_id": entry.entity_id}, "01:00:00")

    freezer.tick(timedelta(hours=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not ran

    await _detach(hass)


async def test_an_entity_already_quiet_is_left_alone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Silence from before the trigger existed does not count.

    Otherwise reloading automations would replay everything that has gone
    quiet since, which is noise rather than news.
    """
    freezer.move_to(dt_util.as_utc(dt_util.parse_datetime("2026-08-27 12:00:00")))
    hass.states.async_set("sensor.probe", "21.5")
    await hass.async_block_till_done()

    # Two hours of silence, and only then does anybody start watching.
    freezer.tick(timedelta(hours=2))
    ran = await _automation(hass, {"entity_id": "sensor.probe"}, "01:00:00")

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not ran

    await _detach(hass)
