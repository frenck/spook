"""Tests for the spook.all_of trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.trigger import TriggerConfig
from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.all_of import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

DOOR = {"trigger": "state", "entity_id": "binary_sensor.door", "to": "on"}
MOTION = {"trigger": "state", "entity_id": "binary_sensor.motion", "to": "on"}
PHONE = {"trigger": "state", "entity_id": "device_tracker.phone", "to": "home"}

FIVE_MINUTES = timedelta(minutes=5)
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
                    "alias": "all together",
                    "trigger": {
                        "platform": "spook.all_of",
                        "options": options
                        or {"triggers": [DOOR, MOTION], "within": "00:05:00"},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {
                                "count": "{{ trigger.triggers | count }}",
                                "first": "{{ trigger.triggers[0].entity_id }}",
                                "last": "{{ trigger.entity_id }}",
                                "span": "{{ trigger.span }}",
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

    The harness fails a test that leaves a listener behind, and this trigger
    holds one nested trigger per member, so this doubles as a check that it
    lets go of all of them.
    """
    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.all_together"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "all_of" in await async_get_triggers(hass)


async def test_one_trigger_is_not_a_set(hass: HomeAssistant) -> None:
    """One trigger combined with nothing is just that trigger."""
    with pytest.raises(vol.Invalid, match="at least 2 triggers"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"triggers": [DOOR], "within": "00:05:00"}}
        )


@pytest.mark.parametrize("within", [{"minutes": 0}, "00:00:00", 0])
async def test_a_zero_window_is_refused(hass: HomeAssistant, within: object) -> None:
    """Nothing can happen inside no time, so the set could never complete."""
    with pytest.raises(vol.Invalid, match="longer than zero"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"triggers": [DOOR, MOTION], "within": within}}
        )


async def test_a_window_is_required(hass: HomeAssistant) -> None:
    """Without one, the set would eventually be complete forever."""
    with pytest.raises(vol.Invalid):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"triggers": [DOOR, MOTION]}}
        )


async def test_both_inside_the_window_fires_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The point of the whole thing."""
    runs = await _automation(hass)

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert runs == []

    freezer.tick(timedelta(minutes=2))
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()

    assert len(runs) == 1
    assert runs[0]["count"] == TWO
    # In the order they were configured, not the order they fired.
    assert runs[0]["first"] == "binary_sensor.door"
    # And the top of the payload is the one that completed the set.
    assert runs[0]["last"] == "binary_sensor.motion"
    assert runs[0]["span"] == "0:02:00"

    await _detach(hass)


async def test_the_order_does_not_matter(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The whole difference from `spook.sequence`."""
    runs = await _automation(hass)

    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    assert len(runs) == 1
    assert runs[0]["last"] == "binary_sensor.door"

    await _detach(hass)


async def test_too_far_apart_is_not_a_set(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Two things an hour apart are not two things happening together."""
    runs = await _automation(hass)

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(hours=1))
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()

    assert runs == []

    await _detach(hass)


async def test_what_fell_out_of_the_window_is_dropped_on_its_own(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """One member going stale does not throw away the others.

    The window slides. The first trigger falls out of it while the other two
    are still counting, so the set completes when the first one comes round
    again and the span is measured from the oldest that is still in.
    """
    runs = await _automation(
        hass,
        {"triggers": [DOOR, MOTION, PHONE], "within": "00:05:00"},
    )

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=4))
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()

    # Six minutes in: the door is now too old, so this is not a set of three.
    freezer.tick(timedelta(minutes=2))
    hass.states.async_set("device_tracker.phone", "home")
    await hass.async_block_till_done()
    assert runs == []

    # The door again, which completes it with the two that are still in.
    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    assert len(runs) == 1
    # Seven minutes in, oldest still counting is the motion at four.
    assert runs[0]["span"] == "0:03:00"

    await _detach(hass)


async def test_it_does_not_fire_again_on_every_firing_after(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Once reported, the set has to happen again in full.

    Left standing, the next turn of any one member would complete the same set
    over and over and the trigger would go off on every event.
    """
    runs = await _automation(hass)

    hass.states.async_set("binary_sensor.door", "on")
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    assert len(runs) == 1

    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()

    assert len(runs) == 1

    await _detach(hass)


async def test_one_member_firing_twice_is_still_one_member(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Every trigger has to have had its turn, not just some of them twice."""
    runs = await _automation(hass)

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()
    assert runs == []

    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()

    assert len(runs) == 1

    await _detach(hass)


async def test_the_payload_carries_the_change_that_completed_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The completing trigger's own context comes through.

    Spook's context conditions read the person off the change that set the run
    going, so handing over a fresh context would make every set read as
    nobody's doing.
    """
    fired: list[tuple[dict, Context | None]] = []

    # Through the trigger's own validation, which is what shapes the nested
    # configs and is the only route that exists in a real house.
    config = await SpookTrigger.async_validate_config(
        hass, {"options": {"triggers": [DOOR, MOTION], "within": "00:05:00"}}
    )
    trigger = SpookTrigger(hass, TriggerConfig(key="all_of", options=config["options"]))

    def _run(payload, _description, context=None) -> None:  # noqa: ANN001
        fired.append((payload, context))

    unsub = await trigger.async_attach_runner(_run)

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    theirs = Context(user_id="abc123")
    hass.states.async_set("binary_sensor.motion", "on", context=theirs)
    await hass.async_block_till_done()

    unsub()

    assert len(fired) == 1
    payload, context = fired[0]
    assert context is theirs
    assert payload["to_state"].entity_id == "binary_sensor.motion"
    assert payload["within"] == FIVE_MINUTES
    assert payload["span"] == timedelta(minutes=1)
    assert [item["entity_id"] for item in payload["triggers"]] == [
        "binary_sensor.door",
        "binary_sensor.motion",
    ]


async def test_a_members_newest_turn_is_the_one_that_counts(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A trigger firing again replaces its earlier turn rather than keeping it.

    The door went half an hour ago and again just now. What this answers is
    whether all of them have happened recently, so the recent one is the one
    that matters. Keeping the first would leave the set stale forever.
    """
    runs = await _automation(hass)

    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=30))
    hass.states.async_set("binary_sensor.door", "off")
    hass.states.async_set("binary_sensor.door", "on")
    await hass.async_block_till_done()

    freezer.tick(timedelta(minutes=1))
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()

    assert len(runs) == 1
    assert runs[0]["span"] == "0:01:00"

    await _detach(hass)


async def test_a_trigger_that_will_not_attach_refuses_the_lot(
    hass: HomeAssistant,
) -> None:
    """One missing member means the set can never be complete.

    Raising is what marks the automation unavailable. Loading it and sitting
    there silent is the failure this is here to avoid.
    """
    config = await SpookTrigger.async_validate_config(
        hass, {"options": {"triggers": [DOOR, MOTION], "within": "00:05:00"}}
    )
    trigger = SpookTrigger(hass, TriggerConfig(key="all_of", options=config["options"]))

    def _run(_payload, _description, _context=None) -> None:  # noqa: ANN001
        """Never called."""

    with (
        patch(
            "custom_components.spook.ectoplasms.spook.triggers.all_of"
            ".async_attach_nested",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError, match="every trigger"),
    ):
        await trigger.async_attach_runner(_run)
