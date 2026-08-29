"""Tests for the light brightness stepping actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.light.services.decrease_brightness import (
    SpookService as DecreaseService,
)
from custom_components.spook.ectoplasms.light.services.increase_brightness import (
    SpookService as IncreaseService,
)

from .conftest import (
    BRIGHT,
    DIM,
    GROUP,
    OFF,
    PLAIN,
    async_set_up_group,
    async_set_up_lights,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# What the lights in the fixtures start at, and where the scale ends.
_DIM = 26
_FULL = 255
_ONE_STEP = 26
_DIMMEST = 1


async def _setup(hass: HomeAssistant) -> None:
    """Set up the lights and both stepping actions."""
    assert await async_setup_component(hass, "homeassistant", {})
    await async_set_up_lights(hass)
    IncreaseService(hass).async_register()
    DecreaseService(hass).async_register()
    await hass.async_block_till_done()


def _brightness(hass: HomeAssistant, entity_id: str) -> int | None:
    """Return what a light is set to right now."""
    return hass.states.get(entity_id).attributes.get("brightness")


async def test_each_light_steps_from_its_own_level(hass: HomeAssistant) -> None:
    """A group keeps its shape rather than levelling out.

    Measured against Home Assistant first: stepping the group entity averages
    its members and sets every one of them to that average, so a room with a
    lamp at 10% and one at 100% ends up with both at 65%.
    """
    await _setup(hass)
    await async_set_up_group(hass, [DIM, BRIGHT])

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": GROUP, "step_pct": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _DIM + _ONE_STEP
    assert _brightness(hass, BRIGHT) == _FULL, "it was already as bright as it goes"


async def test_a_light_that_is_off_is_left_alone(hass: HomeAssistant) -> None:
    """Home Assistant reads an off light as zero and turns it on from there.

    So asking a room for more light switches on everything somebody had
    deliberately turned off. These actions do not switch lights at all.
    """
    await _setup(hass)
    await async_set_up_group(hass, [DIM, OFF])

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": GROUP, "step_pct": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(OFF).state == "off"
    assert _brightness(hass, DIM) == _DIM + _ONE_STEP


async def test_decreasing_stops_at_the_dimmest_a_light_goes(
    hass: HomeAssistant,
) -> None:
    """Rather than switching it off, so holding a button leaves the room lit."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "decrease_brightness",
        {"entity_id": DIM, "step_pct": 100},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(DIM).state == "on"
    assert _brightness(hass, DIM) == _DIMMEST


async def test_increasing_stops_at_full(hass: HomeAssistant) -> None:
    """There is nothing above full brightness to ask for."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": DIM, "step_pct": 100},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _FULL


async def test_a_step_is_required(hass: HomeAssistant) -> None:
    """Without one there is nothing to do."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "light", "increase_brightness", {"entity_id": DIM}, blocking=True
        )


async def test_a_light_with_no_dimmer_is_left_alone(hass: HomeAssistant) -> None:
    """An on-or-off light has no brightness to step.

    It is still a light, so it lands in a group and in an area target like any
    other, and asking it for ten percent more is asking for nothing.
    """
    await _setup(hass)
    await async_set_up_group(hass, [DIM, PLAIN])

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": GROUP, "step_pct": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(PLAIN).state == "on"
    assert "brightness" not in hass.states.get(PLAIN).attributes
    assert _brightness(hass, DIM) == _DIM + _ONE_STEP


async def test_a_light_that_is_off_but_still_reports_a_level_is_left_alone(
    hass: HomeAssistant,
) -> None:
    """Being off is what settles it, not whether a level is on record.

    Home Assistant drops the brightness attribute when a light goes off, but
    not everything that writes a state does: a restored state or a template
    can carry both. Reading the level and ignoring the state would turn such a
    light on.
    """
    await _setup(hass)
    hass.states.async_set(OFF, "off", {"brightness": 128, "color_mode": "brightness"})
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": OFF, "step_pct": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(OFF).state == "off", "it turned on a light that was off"
