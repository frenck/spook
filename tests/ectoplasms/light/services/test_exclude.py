"""Tests for the light actions leaving out what a target excludes."""

# pylint: disable=wrong-import-order
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.light.services.set_brightness import (
    SpookService,
)

from .conftest import BRIGHT, DIM, async_set_up_lights

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

# What the dim light in the fixtures starts at, and what half is.
_DIM = 26
_HALF = 128


async def _setup(hass: HomeAssistant) -> None:
    """Set up the lights and the action."""
    assert await async_setup_component(hass, "homeassistant", {})
    await async_set_up_lights(hass)
    SpookService(hass).async_register()
    await hass.async_block_till_done()


def _brightness(hass: HomeAssistant, entity_id: str) -> int | None:
    """Return what a light is set to right now."""
    return hass.states.get(entity_id).attributes.get("brightness")


async def test_all_takes_every_light(hass: HomeAssistant) -> None:
    """Without an exclude block, `all` still means every light there is."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"entity_id": "all", "brightness_pct": 50},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _HALF
    assert _brightness(hass, BRIGHT) == _HALF


async def test_all_leaves_an_excluded_light_alone(hass: HomeAssistant) -> None:
    """Home Assistant takes the excluded lights off `all`, so these do too.

    The dim light is in two groups as well, and a group is a way back to it.
    """
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"entity_id": "all", "exclude": {"entity_id": DIM}, "brightness_pct": 50},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _DIM, "it adjusted the excluded light"
    assert _brightness(hass, BRIGHT) == _HALF


async def test_all_leaves_an_excluded_area_alone(
    hass: HomeAssistant,
    area_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """An excluded area takes its lights with it."""
    await _setup(hass)
    area = area_registry.async_create("Bedroom")
    entity_registry.async_update_entity(DIM, area_id=area.id)

    await hass.services.async_call(
        "light",
        "set_brightness",
        {"entity_id": "all", "exclude": {"area_id": area.id}, "brightness_pct": 50},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _DIM, "it adjusted a light in the excluded area"
    assert _brightness(hass, BRIGHT) == _HALF


async def test_all_leaves_an_excluded_label_alone(
    hass: HomeAssistant,
    label_registry,  # noqa: ANN001
    entity_registry,  # noqa: ANN001
) -> None:
    """An excluded label takes its lights with it."""
    await _setup(hass)
    label = label_registry.async_create("Night light")
    entity_registry.async_update_entity(DIM, labels={label.label_id})

    await hass.services.async_call(
        "light",
        "set_brightness",
        {
            "entity_id": "all",
            "exclude": {"label_id": label.label_id},
            "brightness_pct": 50,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _DIM, "it adjusted a light with the label"
    assert _brightness(hass, BRIGHT) == _HALF


async def test_a_named_target_leaves_an_excluded_light_alone(
    hass: HomeAssistant,
) -> None:
    """With named lights, Home Assistant's own lookup already subtracts."""
    await _setup(hass)

    await hass.services.async_call(
        "light",
        "set_brightness",
        {
            "entity_id": [DIM, BRIGHT],
            "exclude": {"entity_id": DIM},
            "brightness_pct": 50,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _brightness(hass, DIM) == _DIM, "it adjusted the excluded light"
    assert _brightness(hass, BRIGHT) == _HALF
