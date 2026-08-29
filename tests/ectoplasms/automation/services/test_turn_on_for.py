"""Tests for the automation.turn_on_for action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.core import Context, CoreState, State
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache,
)
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.automation.services.turn_on_for import (
    SpookService,
)
from custom_components.spook.timed_states import async_setup_timed_states

# Importing Spook puts it in `sys.modules`, which is what lets Home Assistant's
# loader resolve the integration.
import custom_components.spook  # noqa: F401  # pylint: disable=unused-import

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

    from homeassistant.core import HomeAssistant

TONIGHT = "automation.tonight"
OTHER = "automation.other"
AN_HOUR = timedelta(hours=1)

CONFIG = {
    "automation": [
        {
            "id": name,
            "alias": name.title(),
            "triggers": [{"trigger": "state", "entity_id": "input_boolean.x"}],
            "actions": [],
        }
        for name in ("tonight", "other")
    ]
}


async def _setup(hass: HomeAssistant) -> None:
    """Set up the automations, off, plus the register and the action."""
    mock_restore_cache(hass, (State(TONIGHT, "off"), State(OTHER, "off")))

    assert await async_setup_component(hass, "automation", CONFIG)
    await hass.async_block_till_done()

    hass.set_state(CoreState.running)
    await async_setup_timed_states(hass)
    SpookService(hass).async_register()
    await hass.async_block_till_done()


async def test_it_turns_the_targeted_automation_on(hass: HomeAssistant) -> None:
    """The action is what a person or an automation actually calls."""
    await _setup(hass)

    await hass.services.async_call(
        "automation",
        "turn_on_for",
        {"entity_id": TONIGHT, "duration": {"hours": 1}},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(TONIGHT).state == "on"
    assert hass.states.get(OTHER).state == "off", "it turned something else on too"

    hass.data["spook_timed_states"].async_stop()


async def test_it_turns_it_back_off_when_the_time_is_up(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Which is the half an automation cannot do for itself."""
    await _setup(hass)

    await hass.services.async_call(
        "automation",
        "turn_on_for",
        {"entity_id": [TONIGHT, OTHER], "duration": {"hours": 1}},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(TONIGHT).state == "on"
    assert hass.states.get(OTHER).state == "on"

    freezer.tick(AN_HOUR + timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(TONIGHT).state == "off"
    assert hass.states.get(OTHER).state == "off"

    hass.data["spook_timed_states"].async_stop()


async def test_the_caller_travels_with_the_switching_on(hass: HomeAssistant) -> None:
    """An automation watching this one switch on can still tell who asked."""
    await _setup(hass)

    asked = Context()
    await hass.services.async_call(
        "automation",
        "turn_on_for",
        {"entity_id": TONIGHT, "duration": {"hours": 1}},
        blocking=True,
        context=asked,
    )
    await hass.async_block_till_done()

    assert hass.states.get(TONIGHT).context.id == asked.id

    hass.data["spook_timed_states"].async_stop()


async def test_a_run_of_nothing_is_refused(hass: HomeAssistant) -> None:
    """It would turn an automation on and straight back off, for nothing."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "automation",
            "turn_on_for",
            {"entity_id": TONIGHT, "duration": {"seconds": 0}},
            blocking=True,
        )

    assert hass.states.get(TONIGHT).state == "off"
    assert hass.data["spook_timed_states"].async_until(TONIGHT) is None

    hass.data["spook_timed_states"].async_stop()


async def test_a_duration_is_required(hass: HomeAssistant) -> None:
    """Without one there is no time limit, only an on switch."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "automation", "turn_on_for", {"entity_id": TONIGHT}, blocking=True
        )

    assert hass.states.get(TONIGHT).state == "off"

    hass.data["spook_timed_states"].async_stop()
