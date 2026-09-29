"""Tests for the zone.delete service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.zone import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.zone.services import delete

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _zone(zone_id: str, name: str) -> dict[str, Any]:
    """Return a zone as the storage collection keeps it."""
    return {
        "id": zone_id,
        "name": name,
        "latitude": 52.37,
        "longitude": 4.89,
        "radius": 100,
        "passive": False,
        "icon": "mdi:map-marker",
    }


@pytest.fixture(autouse=True)
async def _zones(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up two editable zones, and register the Spook delete service."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {"items": [_zone("work", "Work"), _zone("gym", "Gym")]},
    }
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    delete.SpookService(hass).async_register()


async def test_delete_removes_the_zones(hass: HomeAssistant) -> None:
    """Every zone in the list is deleted."""
    await hass.services.async_call(
        DOMAIN,
        "delete",
        {ATTR_ENTITY_ID: ["zone.work", "zone.gym"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("zone.work") is None
    assert hass.states.get("zone.gym") is None


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ("zone.nowhere", "Could not find entity_id"),
        ("zone.home", "not editable"),
    ],
)
async def test_a_bad_zone_in_a_list_deletes_none_of_them(
    hass: HomeAssistant,
    bad: str,
    message: str,
) -> None:
    """A zone that cannot go, late in the list, keeps the ones before it.

    They used to be deleted already by the time the bad one turned up, and a
    deleted zone does not come back.
    """
    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            DOMAIN,
            "delete",
            {ATTR_ENTITY_ID: ["zone.work", bad]},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get("zone.work") is not None
