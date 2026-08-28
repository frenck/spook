"""Tests for the spook.wait_for_condition action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.spook.services.wait_for_condition import (
    SpookService,
)

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

GATE = {"condition": "state", "entity_id": "input_boolean.gate", "state": "on"}
SETTLE = 0.05


def _register(hass: HomeAssistant) -> None:
    """Register the action, the way Spook's service manager would."""
    SpookService(hass).async_register()


async def _wait(hass: HomeAssistant, **data: object) -> dict:
    """Call the action and hand back its response."""
    return await hass.services.async_call(
        DOMAIN,
        "wait_for_condition",
        {"condition": GATE, **data},
        blocking=True,
        return_response=True,
    )


async def test_it_returns_at_once_when_already_true(hass: HomeAssistant) -> None:
    """The case `wait_for_trigger` cannot cover without an `if` around it.

    That one always waits for something to happen, so people guard it. This
    checks first, which is what `wait_template` does too.
    """
    _register(hass)
    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()

    # With a timeout, so that losing the check-first fails this in a second
    # rather than hanging the suite waiting for something that already
    # happened.
    assert await _wait(hass, timeout={"seconds": 1}) == {"completed": True}


async def test_it_waits_until_the_condition_turns_true(hass: HomeAssistant) -> None:
    """And it really waits: the caller does not come back until it turns.

    On the real clock, because the point is that the call is still pending.
    """
    _register(hass)
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    waiting = hass.async_create_task(_wait(hass))
    await asyncio.sleep(SETTLE)
    assert not waiting.done(), "came back before the condition was true"

    hass.states.async_set("input_boolean.gate", "on")
    await asyncio.sleep(SETTLE)

    assert waiting.done(), "did not come back once the condition turned true"
    assert waiting.result() == {"completed": True}


async def test_it_gives_up_after_the_timeout(hass: HomeAssistant) -> None:
    """A timeout is an answer, not a failure: it says it did not happen."""
    _register(hass)
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    assert await _wait(hass, timeout={"seconds": 1}) == {"completed": False}


async def test_a_condition_turning_true_beats_the_timeout(
    hass: HomeAssistant,
) -> None:
    """With time to spare, the answer is the condition and not the clock."""
    _register(hass)
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    waiting = hass.async_create_task(_wait(hass, timeout={"seconds": 30}))
    await asyncio.sleep(SETTLE)
    hass.states.async_set("input_boolean.gate", "on")
    await asyncio.sleep(SETTLE)

    assert waiting.done()
    assert waiting.result() == {"completed": True}


async def test_it_takes_the_ordinary_building_blocks(hass: HomeAssistant) -> None:
    """The whole point: waiting on a condition without writing a template."""
    _register(hass)
    hass.states.async_set("input_boolean.gate", "on")
    hass.states.async_set("sensor.temp", "10")
    await hass.async_block_till_done()

    response = await hass.services.async_call(
        DOMAIN,
        "wait_for_condition",
        {
            "condition": {
                "condition": "and",
                "conditions": [
                    GATE,
                    {
                        "condition": "numeric_state",
                        "entity_id": "sensor.temp",
                        "above": 20,
                    },
                ],
            },
            "timeout": {"seconds": 1},
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"completed": False}, "passed on half the condition"


async def test_a_bad_condition_is_reported(hass: HomeAssistant) -> None:
    """Not swallowed, and not waited on forever either."""
    _register(hass)

    with pytest.raises(HomeAssistantError, match="Invalid condition"):
        await hass.services.async_call(
            DOMAIN,
            "wait_for_condition",
            {"condition": {"condition": "not_a_condition"}},
            blocking=True,
            return_response=True,
        )


async def test_it_can_be_waited_on_from_a_script(hass: HomeAssistant) -> None:
    """A script waits for it, which is the placement this is built for.

    Home Assistant calls a service action from a script with `blocking=True`
    and awaits it, so an action that waits holds the sequence up. That is what
    makes this possible without touching the script engine.
    """
    _register(hass)
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    done: list[str] = []
    hass.services.async_register(
        "test", "mark", lambda call: done.append(call.data["at"])
    )

    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "patient": {
                    "sequence": [
                        {"action": "test.mark", "data": {"at": "before"}},
                        {
                            "action": f"{DOMAIN}.wait_for_condition",
                            "data": {"condition": GATE},
                        },
                        {"action": "test.mark", "data": {"at": "after"}},
                    ]
                }
            }
        },
    )
    await hass.async_block_till_done()

    running = hass.async_create_task(
        hass.services.async_call("script", "patient", blocking=True)
    )
    await asyncio.sleep(SETTLE)
    assert done == ["before"], "the script did not stop at the wait"

    hass.states.async_set("input_boolean.gate", "on")
    await asyncio.sleep(SETTLE)
    await running

    assert done == ["before", "after"], "the script never carried on"
