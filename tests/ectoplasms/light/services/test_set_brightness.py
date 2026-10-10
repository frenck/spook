"""Tests for the light set brightness action."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.light.services.set_brightness import (
    SpookService,
)

from .conftest import BRIGHT, DIM, GROUP, OFF, async_set_up_group, async_set_up_lights

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_HALF = 128


async def _setup(hass: HomeAssistant) -> None:
    """Set up the lights and the action."""
    assert await async_setup_component(hass, "homeassistant", {})
    await async_set_up_lights(hass)
    SpookService(hass).async_register()
    await hass.async_block_till_done()


async def test_it_sets_the_lights_that_are_on(hass: HomeAssistant) -> None:
    """`light.turn_on` sets the level and switches the light on, both at once.

    Adjusting a room usually means the first without the second, and there is
    no way to ask Home Assistant for that.
    """
    await _setup(hass)
    await async_set_up_group(hass, [DIM, BRIGHT, OFF])

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"entity_id": GROUP, "brightness_pct": 50},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(DIM).attributes["brightness"] == _HALF
    assert hass.states.get(BRIGHT).attributes["brightness"] == _HALF
    assert hass.states.get(OFF).state == "off", "it switched on a light that was off"


async def test_a_transition_is_passed_along(hass: HomeAssistant) -> None:
    """Because a jump to half brightness is not what anybody wants to watch."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"entity_id": DIM, "brightness_pct": 50, "transition": 2},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.data["entity_components"]["light"].get_entity(DIM)
    assert light.transitions == [2.0]


async def test_a_brightness_is_required(hass: HomeAssistant) -> None:
    """Without one there is nothing to set."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "light", "set_brightness", {"entity_id": DIM}, blocking=True
        )
