"""Tests for the light colour, colour temperature and effect actions."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component
import pytest
import voluptuous as vol

from custom_components.spook.ectoplasms.light.services.set_color import (
    SpookService as ColourService,
)
from custom_components.spook.ectoplasms.light.services.set_color_temperature import (
    SpookService as TemperatureService,
)
from custom_components.spook.ectoplasms.light.services.set_effect import (
    SpookService as EffectService,
)

from .conftest import COLOUR, DIM, OFF, WHITES, async_set_up_group, async_set_up_lights

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_CORAL = [255, 127, 80]
_WARM = 2700
_TOO_COOL = 6500
_COOLEST_IT_GOES = 4000


async def _setup(hass: HomeAssistant) -> None:
    """Set up the lights and the three actions."""
    assert await async_setup_component(hass, "homeassistant", {})
    await async_set_up_lights(hass)
    ColourService(hass).async_register()
    TemperatureService(hass).async_register()
    EffectService(hass).async_register()
    await hass.async_block_till_done()


def _light(hass: HomeAssistant, entity_id: str):  # noqa: ANN202
    """Return the entity object behind an entity ID."""
    return hass.data["entity_components"]["light"].get_entity(entity_id)


async def test_colour_skips_lights_that_cannot_do_colour(
    hass: HomeAssistant,
) -> None:
    """`light.turn_on` with a colour turns a white-only light on white instead.

    Which is a visible change to a light somebody was not asking about, in a
    room where one lamp happens to do colour and the rest do not.
    """
    await _setup(hass)
    await async_set_up_group(hass, [COLOUR, WHITES, DIM])

    await hass.services.async_call(
        "light",
        "set_color",
        {"entity_id": "light.kitchen", "rgb_color": _CORAL},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(COLOUR).attributes["rgb_color"] == tuple(_CORAL)
    assert not _light(hass, WHITES).calls, "it went at a light with no colour"


async def test_colour_leaves_a_light_that_is_off_alone(hass: HomeAssistant) -> None:
    """The same promise as the rest of these: adjust, do not switch."""
    await _setup(hass)
    await async_set_up_group(hass, [COLOUR, OFF])

    await hass.services.async_call(
        "light",
        "set_color",
        {"entity_id": "light.kitchen", "rgb_color": _CORAL},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(OFF).state == "off"


async def test_a_colour_is_required(hass: HomeAssistant) -> None:
    """Without one there is nothing to set."""
    await _setup(hass)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "light", "set_color", {"entity_id": COLOUR}, blocking=True
        )


async def test_colour_temperature_is_held_to_what_a_light_can_reach(
    hass: HomeAssistant,
) -> None:
    """Warm white on one lamp is a number another one cannot reach.

    A group is rarely all the same model, so asking for daylight would
    otherwise be an error on half of them or a silent nothing.
    """
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "set_color_temperature",
        {"entity_id": WHITES, "kelvin": _TOO_COOL},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(WHITES).attributes["color_temp_kelvin"] == _COOLEST_IT_GOES


async def test_colour_temperature_skips_lights_that_cannot_do_it(
    hass: HomeAssistant,
) -> None:
    """A colour-only light has no white range to sit in."""
    await _setup(hass)
    await async_set_up_group(hass, [WHITES, COLOUR])

    await hass.services.async_call(
        "light",
        "set_color_temperature",
        {"entity_id": "light.kitchen", "kelvin": _WARM},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert not _light(hass, COLOUR).calls, "it went at a light with no white range"


async def test_an_effect_only_goes_to_lights_that_have_it(
    hass: HomeAssistant,
) -> None:
    """Effect names are per manufacturer and rarely agree.

    Sending one to a light that has never heard of it is an error from the
    integration, or a light that quietly does nothing.
    """
    await _setup(hass)
    await async_set_up_group(hass, [COLOUR, WHITES])

    await hass.services.async_call(
        "light",
        "set_effect",
        {"entity_id": "light.kitchen", "effect": "Colorloop"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(COLOUR).attributes["effect"] == "Colorloop"
    assert not _light(hass, WHITES).calls, "it sent an effect to a light without any"


async def test_an_effect_nothing_knows_changes_nothing(hass: HomeAssistant) -> None:
    """Rather than being passed on for the integration to refuse."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "set_effect",
        {"entity_id": COLOUR, "effect": "Disco Inferno"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert not _light(hass, COLOUR).calls
