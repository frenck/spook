"""Tests for moving and resizing the home zone through zone.update."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from homeassistant.components.zone import DOMAIN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.zone.services import update

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def _zones(hass: HomeAssistant) -> None:
    """Set up zones, the home zone included, and register the action."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    update.SpookService(hass).async_register()


async def test_the_home_zone_can_be_moved_and_resized(hass: HomeAssistant) -> None:
    """Discussion #1129: the home zone, changed from an automation.

    It is the location of the whole house, so that is what moves, and the
    home zone follows it.
    """
    await hass.services.async_call(
        DOMAIN,
        "update",
        {
            "entity_id": "zone.home",
            "latitude": 52.37,
            "longitude": 4.89,
            "radius": 250,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    assert (hass.config.latitude, hass.config.longitude) == (52.37, 4.89)
    assert hass.config.radius == 250  # noqa: PLR2004
    attributes = hass.states.get("zone.home").attributes
    assert (attributes["latitude"], attributes["longitude"]) == (52.37, 4.89)
    assert attributes["radius"] == 250  # noqa: PLR2004


async def test_only_the_radius_can_change(hass: HomeAssistant) -> None:
    """What is left out stays as it was."""
    before = (hass.config.latitude, hass.config.longitude)

    await hass.services.async_call(
        DOMAIN, "update", {"entity_id": "zone.home", "radius": 300}, blocking=True
    )
    await hass.async_block_till_done()

    assert (hass.config.latitude, hass.config.longitude) == before
    assert hass.states.get("zone.home").attributes["radius"] == 300  # noqa: PLR2004


@pytest.mark.parametrize(
    "data", [{"name": "Castle"}, {"icon": "mdi:castle"}, {"passive": True}]
)
async def test_what_the_home_zone_cannot_take_is_refused(
    hass: HomeAssistant, data: dict
) -> None:
    """Its name is the name of the whole house, and it is never passive."""
    with pytest.raises(HomeAssistantError, match="only takes a latitude"):
        await hass.services.async_call(
            DOMAIN, "update", {"entity_id": "zone.home", **data}, blocking=True
        )


async def test_a_fraction_of_a_meter_is_refused(hass: HomeAssistant) -> None:
    """Home Assistant keeps the radius in whole meters, and 150.5 is not one."""
    before = hass.config.radius

    with pytest.raises(HomeAssistantError, match="whole meters"):
        await hass.services.async_call(
            DOMAIN, "update", {"entity_id": "zone.home", "radius": 150.5}, blocking=True
        )

    assert hass.config.radius == before
