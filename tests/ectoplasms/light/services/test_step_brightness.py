"""Tests for the light brightness stepping actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

import asyncio
from functools import partial

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
    EMPTY_GROUP,
    GROUP,
    OFF,
    OWNED_GROUP,
    SET_GROUP,
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


async def test_a_transition_is_passed_along(hass: HomeAssistant) -> None:
    """Because a jump to a new level is not what anybody wants to watch."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": DIM, "step_pct": 10, "transition": 2},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.data["entity_components"]["light"].get_entity(DIM)
    assert light.transitions == [2.0]


async def test_lights_are_stepped_together_rather_than_one_after_another(
    hass: HomeAssistant,
) -> None:
    """A room full of lights should not take as long as all of them added up.

    Every light lands on its own level, so this cannot be a single call, but
    it does not have to wait for each one either. Slow lights are exactly the
    ones somebody notices while dimming.
    """
    await _setup(hass)
    await async_set_up_group(hass, [DIM, BRIGHT])

    started = asyncio.Event()
    both_in_flight = asyncio.Event()
    in_flight = 0

    lights = hass.data["entity_components"]["light"]
    originals = {
        entity_id: lights.get_entity(entity_id).async_turn_on
        for entity_id in (DIM, BRIGHT)
    }

    async def _slow(entity_id: str, **kwargs: object) -> None:
        nonlocal in_flight
        in_flight += 1
        started.set()

        if in_flight == 2:  # noqa: PLR2004
            both_in_flight.set()

        await both_in_flight.wait()
        await originals[entity_id](**kwargs)

    for entity_id in (DIM, BRIGHT):
        entity = lights.get_entity(entity_id)
        entity.async_turn_on = partial(_slow, entity_id)  # type: ignore[method-assign]

    async with asyncio.timeout(5):
        await hass.services.async_call(
            "light",
            "increase_brightness",
            {"entity_id": GROUP, "step_pct": 10},
            blocking=True,
        )

    assert both_in_flight.is_set(), "the second light waited for the first to finish"


async def test_a_group_an_integration_owns_is_worked_through_too(
    hass: HomeAssistant,
) -> None:
    """Not every light group keeps its members under the same attribute.

    A helper group lists entity IDs under `entity_id`. A group belonging to
    one integration, like the ones MQTT builds, gets `group_entities` from
    Home Assistant itself. Reading only the first sort means stepping the
    second sort's group entity, which is the averaging this exists to avoid.
    """
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": OWNED_GROUP, "step_pct": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _DIM + _ONE_STEP
    assert _brightness(hass, BRIGHT) == _FULL


async def test_a_group_with_no_members_is_not_a_light(hass: HomeAssistant) -> None:
    """An empty group is still a group, and has no level worth setting.

    Reading its members as "does it hold anything" rather than "does it say
    what it holds" would drop it through to the plain-light case, and step the
    group entity itself.
    """
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": EMPTY_GROUP, "step_pct": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, EMPTY_GROUP) == _DIM, "it stepped the group itself"


async def test_a_group_that_hands_its_members_out_as_a_set(
    hass: HomeAssistant,
) -> None:
    """Hue keeps its members under `entity_id`, but in a set rather than a list.

    Insisting on a list means a Hue room falls through to the plain-light path
    and gets stepped from its own averaged level, which is core#118009 all over
    again.
    """
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "increase_brightness",
        {"entity_id": SET_GROUP, "step_pct": 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _DIM + _ONE_STEP
    assert _brightness(hass, BRIGHT) == _FULL
