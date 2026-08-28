"""Tests for the spook.while trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.helpers import selector
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.spook.triggers.while_ import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

OPEN = {"condition": "state", "entity_id": "cover.garage", "state": "open"}
EVERY = timedelta(minutes=10)

TWICE = 2
THRICE = 3


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
                    "alias": "nagging",
                    "trigger": {
                        "platform": "spook.while",
                        "options": options
                        or {"condition": OPEN, "every": {"minutes": 10}},
                    },
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {"times": "{{ trigger.times }}"},
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
        "automation", "turn_off", {"entity_id": "automation.nagging"}, blocking=True
    )
    await hass.async_block_till_done()


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let one interval pass."""
    freezer.tick(EVERY)
    async_fire_time_changed(hass, dt_util.utcnow() + EVERY)
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "while" in await async_get_triggers(hass)


async def test_it_fires_on_arrival_and_keeps_going(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The whole point: it arrives, and then it nags."""
    hass.states.async_set("cover.garage", "closed")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    assert not runs, "fired while the condition was false"

    hass.states.async_set("cover.garage", "open")
    await hass.async_block_till_done()
    assert len(runs) == 1, "did not fire when the condition arrived"

    await _tick(hass, freezer)
    assert len(runs) == TWICE

    await _tick(hass, freezer)
    assert len(runs) == THRICE

    await _detach(hass)


async def test_it_stops_when_the_condition_stops(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A nag about something that is no longer true is just noise."""
    hass.states.async_set("cover.garage", "closed")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    hass.states.async_set("cover.garage", "open")
    await hass.async_block_till_done()
    await _tick(hass, freezer)
    assert len(runs) == TWICE

    hass.states.async_set("cover.garage", "closed")
    await hass.async_block_till_done()

    await _tick(hass, freezer)
    await _tick(hass, freezer)
    assert len(runs) == TWICE, "it kept nagging after the condition let go"

    await _detach(hass)


async def test_it_starts_over_the_next_time(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Counting from one again, because this is a new spell of it."""
    hass.states.async_set("cover.garage", "closed")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    hass.states.async_set("cover.garage", "open")
    await hass.async_block_till_done()
    await _tick(hass, freezer)
    hass.states.async_set("cover.garage", "closed")
    await hass.async_block_till_done()

    hass.states.async_set("cover.garage", "open")
    await hass.async_block_till_done()

    assert [run["times"] for run in runs] == [1, TWICE, 1]

    await _detach(hass)


async def test_it_does_not_fire_for_a_condition_already_true(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Loading an automation is not the condition arriving.

    The same call `condition_met` makes, and for the same reason: every
    reload would otherwise set off every automation whose condition holds.
    """
    hass.states.async_set("cover.garage", "open")
    await hass.async_block_till_done()
    runs = await _automation(hass)

    assert not runs

    await _tick(hass, freezer)
    assert not runs, "it started nagging about a condition that was already true"

    await _detach(hass)


async def test_it_carries_the_user_through_on_arrival(
    hass: HomeAssistant,
) -> None:
    """Whoever caused the condition to arrive set the first run going."""
    user = await hass.auth.async_create_user("Ghost Hunter")
    hass.states.async_set("cover.garage", "closed")
    await hass.async_block_till_done()

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
                        "platform": "spook.while",
                        "options": {"condition": OPEN, "every": {"minutes": 10}},
                    },
                    "condition": [{"condition": f"spook.{which}"}],
                    "action": [{"action": "test.mark", "data": {"which": which}}],
                }
                for which in ("triggered_by_user", "not_triggered_by_user")
            ]
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set("cover.garage", "open", context=Context(user_id=user.id))
    await hass.async_block_till_done()

    assert ran == ["triggered_by_user"]

    for alias in ("triggered_by_user", "not_triggered_by_user"):
        await hass.services.async_call(
            "automation",
            "turn_off",
            {"entity_id": f"automation.{alias}"},
            blocking=True,
        )
    await hass.async_block_till_done()


async def test_a_repeat_names_nobody(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Nobody causes the clock to come round, so nobody is behind a repeat."""
    hass.states.async_set("cover.garage", "closed")
    await hass.async_block_till_done()

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
                    "alias": "not_triggered_by_user",
                    "trigger": {
                        "platform": "spook.while",
                        "options": {"condition": OPEN, "every": {"minutes": 10}},
                    },
                    "condition": [{"condition": "spook.not_triggered_by_user"}],
                    "action": [
                        {
                            "action": "test.mark",
                            "data": {"which": "{{ trigger.times }}"},
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()

    hass.states.async_set(
        "cover.garage", "open", context=Context(user_id="ghost-hunter")
    )
    await hass.async_block_till_done()
    assert not ran, "the arrival was attributed to nobody"

    await _tick(hass, freezer)
    assert ran == [TWICE], "the repeat was attributed to somebody"

    await hass.services.async_call(
        "automation",
        "turn_off",
        {"entity_id": "automation.not_triggered_by_user"},
        blocking=True,
    )
    await hass.async_block_till_done()


async def test_it_takes_what_the_condition_selector_produces(
    hass: HomeAssistant,
) -> None:
    """The shape an automation built in the user interface actually has."""
    hass.states.async_set("cover.garage", "closed")
    await hass.async_block_till_done()

    runs = await _automation(
        hass,
        {
            "condition": selector.ConditionSelector()(OPEN),
            "every": {"minutes": 10},
        },
    )

    assert hass.states.get("automation.nagging").state == "on", (
        "the automation did not load"
    )

    hass.states.async_set("cover.garage", "open")
    await hass.async_block_till_done()
    assert len(runs) == 1

    await _detach(hass)


async def test_an_interval_is_required(hass: HomeAssistant) -> None:
    """Without one this is just `condition_met`."""
    with pytest.raises(vol.Invalid, match="required key"):
        await SpookTrigger.async_validate_config(hass, {"options": {"condition": OPEN}})


async def test_a_zero_interval_is_refused(hass: HomeAssistant) -> None:
    """It would fire as fast as Home Assistant can run it."""
    with pytest.raises(vol.Invalid, match="as fast as"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"condition": OPEN, "every": {"seconds": 0}}}
        )


async def test_a_condition_is_required(hass: HomeAssistant) -> None:
    """Without one there is nothing to hold."""
    with pytest.raises(vol.Invalid, match="required key"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"every": {"minutes": 10}}}
        )


async def test_a_run_dependent_condition_is_refused(hass: HomeAssistant) -> None:
    """The same refusal the other condition watchers make."""
    with pytest.raises(vol.Invalid, match="no run here"):
        await SpookTrigger.async_validate_config(
            hass,
            {
                "options": {
                    "condition": {"condition": "trigger", "id": "abc"},
                    "every": {"minutes": 10},
                }
            },
        )
