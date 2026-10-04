"""Tests for the light actions on platforms that do one call at a time."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.exceptions import Unauthorized
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
    from pytest_homeassistant_custom_component.common import MockUser

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


async def test_rights_are_checked_before_anything_changes(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test somebody who may not control a light gets refused, up front.

    As an entity action, Home Assistant checked every target first. Done one
    light at a time, the allowed ones would already have changed by the time
    one that is not refused the lot.
    """
    await _setup(hass)
    # Allowed the bright light, and not the dim one.
    hass_read_only_user.mock_policy({"entities": {"entity_ids": {BRIGHT: True}}})

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "light",
            "set_brightness",
            {"entity_id": [BRIGHT, DIM], "brightness_pct": 50},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert hass.states.get(BRIGHT).attributes["brightness"] == _FULL
    assert hass.states.get(DIM).attributes["brightness"] == _DIM_LEVEL


async def test_all_is_what_somebody_may_control(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test `all` passes over lights somebody may not control, not refuses."""
    await _setup(hass)
    hass_read_only_user.mock_policy({"entities": {"entity_ids": {BRIGHT: True}}})

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"entity_id": "all", "brightness_pct": 50},
        blocking=True,
        context=Context(user_id=hass_read_only_user.id),
    )

    # The one they may control is set, the other left alone.
    assert hass.states.get(BRIGHT).attributes["brightness"] == _HALF
    assert hass.states.get(DIM).attributes["brightness"] == _DIM_LEVEL


async def test_an_administrator_may_control_everything(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test an administrator's call goes through as before."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"entity_id": BRIGHT, "brightness_pct": 50},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert hass.states.get(BRIGHT).attributes["brightness"] == _HALF
