"""Tests for the light actions on platforms that do one call at a time."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.setup import async_setup_component
import pytest

from custom_components.spook.ectoplasms.light.services import (
    decrease_brightness,
    increase_brightness,
    set_brightness,
    set_color,
    set_color_temperature,
    set_effect,
)

from .conftest import BRIGHT, COLOUR, DIM, WHITES, async_set_up_lights

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import (
        area_registry as ar,
        entity_registry as er,
    )

# Where the dim light already is, and half and full, in the brightness
# numbers a light keeps.
_DIM_LEVEL = 26
_HALF = 128
_FULL = 255

_ACTIONS = (
    decrease_brightness,
    increase_brightness,
    set_brightness,
    set_color,
    set_color_temperature,
    set_effect,
)


async def _setup(hass: HomeAssistant) -> None:
    """Set up the lights on a one-call-at-a-time platform, and the actions."""
    assert await async_setup_component(hass, "homeassistant", {})
    await async_set_up_lights(hass, parallel_updates=1)
    for action in _ACTIONS:
        action.SpookService(hass).async_register()
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("service", "data", "target"),
    [
        ("decrease_brightness", {"step_pct": 10}, DIM),
        ("increase_brightness", {"step_pct": 10}, DIM),
        ("set_brightness", {"brightness_pct": 50}, DIM),
        ("set_color", {"rgb_color": [255, 0, 0]}, COLOUR),
        ("set_color_temperature", {"kelvin": 3000}, WHITES),
        ("set_effect", {"effect": "Colorloop"}, COLOUR),
    ],
)
async def test_the_actions_do_not_wait_on_themselves(
    hass: HomeAssistant, service: str, data: dict[str, Any], target: str
) -> None:
    """Test none of the actions hangs on a one-call-at-a-time platform.

    Home Assistant runs an entity action holding its platform's lock, and
    `light.turn_on` waits for that lock. As entity actions these waited on
    each other for ever.
    """
    await _setup(hass)

    async with asyncio.timeout(5):
        await hass.services.async_call(
            "light", service, {"entity_id": target, **data}, blocking=True
        )


async def test_an_area_reaches_its_lights(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the lights in an area are found, now the action looks for them."""
    await _setup(hass)
    kitchen = area_registry.async_create("Kitchen")
    entity_registry.async_update_entity(BRIGHT, area_id=kitchen.id)

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"area_id": kitchen.id, "brightness_pct": 50},
        blocking=True,
    )

    # The light in the kitchen is set, the one elsewhere is left as it was.
    assert hass.states.get(BRIGHT).attributes["brightness"] == _HALF
    assert hass.states.get(DIM).attributes["brightness"] == _DIM_LEVEL


async def test_all_reaches_every_light_that_is_on(hass: HomeAssistant) -> None:
    """Test `entity_id: all` still means every light."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"entity_id": "all", "brightness_pct": 100},
        blocking=True,
    )

    assert hass.states.get(DIM).attributes["brightness"] == _FULL
    assert hass.states.get(BRIGHT).attributes["brightness"] == _FULL
