"""Tests for the spook.condition_met trigger."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.spook.triggers.condition_met import SpookTrigger
from custom_components.spook.trigger import async_get_triggers

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration when it goes looking for the trigger platform.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

GATE = {"condition": "state", "entity_id": "input_boolean.gate", "state": "on"}
TWICE = 2


async def _automation(hass: HomeAssistant, condition: dict | None = None) -> list[int]:
    """Set up an automation on the trigger and record every run."""
    ran: list[int] = []
    hass.services.async_register("test", "mark", lambda _call: ran.append(1))

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "when true",
                    "trigger": {
                        "platform": "spook.condition_met",
                        "options": {"condition": condition or GATE},
                    },
                    "action": [{"action": "test.mark"}],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    return ran


async def _detach(hass: HomeAssistant) -> None:
    """Turn the automation off, which detaches its trigger.

    The harness fails a test that leaves a timer or listener behind, and this
    trigger holds both, so this doubles as a check that it clears up.
    """
    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "automation.when_true"}, blocking=True
    )
    await hass.async_block_till_done()


async def test_the_trigger_is_discovered(hass: HomeAssistant) -> None:
    """The trigger turns up in Spook's discovery, under a plain key."""
    assert "condition_met" in await async_get_triggers(hass)


async def test_it_fires_when_the_condition_turns_true(hass: HomeAssistant) -> None:
    """False to true is the event, and it happens again the next time."""
    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    ran = await _automation(hass)
    assert not ran

    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert len(ran) == 1

    hass.states.async_set("input_boolean.gate", "off")
    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert len(ran) == TWICE

    await _detach(hass)


async def test_it_does_not_fire_for_a_condition_already_true(
    hass: HomeAssistant,
) -> None:
    """Loading an automation is not the condition turning true.

    Otherwise every reload would set off every automation whose condition
    happens to hold, which is how the template trigger behaves too.
    """
    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()

    ran = await _automation(hass)

    assert not ran, "fired just for loading while the condition was already true"

    await _detach(hass)


async def test_it_does_not_fire_when_the_condition_turns_false(
    hass: HomeAssistant,
) -> None:
    """Only one of the two turns is the event."""
    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()

    ran = await _automation(hass)

    hass.states.async_set("input_boolean.gate", "off")
    await hass.async_block_till_done()

    assert not ran

    await _detach(hass)


async def test_it_takes_the_ordinary_building_blocks(hass: HomeAssistant) -> None:
    """The whole point: a condition nobody would want to write as a template."""
    hass.states.async_set("input_boolean.gate", "off")
    hass.states.async_set("sensor.temp", "10")
    await hass.async_block_till_done()

    ran = await _automation(
        hass,
        {
            "condition": "and",
            "conditions": [
                GATE,
                {"condition": "numeric_state", "entity_id": "sensor.temp", "above": 20},
            ],
        },
    )

    hass.states.async_set("input_boolean.gate", "on")
    await hass.async_block_till_done()
    assert not ran, "fired on half the condition"

    hass.states.async_set("sensor.temp", "25")
    await hass.async_block_till_done()
    assert len(ran) == 1

    await _detach(hass)


async def test_a_condition_is_required(hass: HomeAssistant) -> None:
    """Without one there is nothing to watch."""
    with pytest.raises(Exception, match="required key"):
        await SpookTrigger.async_validate_config(hass, {"options": {}})


async def test_a_bad_condition_takes_down_only_its_own_automation(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A condition that cannot be built is reported, not swallowed.

    And it costs that automation only: the others keep working, which is what
    makes validating up front worth doing.
    """
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "fine",
                    "trigger": {
                        "platform": "spook.condition_met",
                        "options": {"condition": GATE},
                    },
                    "action": [],
                },
                {
                    "alias": "broken",
                    "trigger": {
                        "platform": "spook.condition_met",
                        "options": {"condition": {"condition": "not_a_condition"}},
                    },
                    "action": [],
                },
            ]
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("automation.fine").state == "on"
    assert hass.states.get("automation.broken").state == "unavailable"
    assert "not_a_condition" in caplog.text

    await hass.services.async_call(
        "automation", "turn_off", {"entity_id": "automation.fine"}, blocking=True
    )
    await hass.async_block_till_done()


async def test_validation_refuses_a_condition_that_does_not_exist(
    hass: HomeAssistant,
) -> None:
    """The refusal comes from Home Assistant, as a `HomeAssistantError`."""
    with pytest.raises(HomeAssistantError, match="Invalid condition"):
        await SpookTrigger.async_validate_config(
            hass, {"options": {"condition": {"condition": "not_a_condition"}}}
        )
