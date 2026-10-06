"""Tests for passive zones through zone.create and zone.update."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from homeassistant.components.zone import DOMAIN
from homeassistant.setup import async_setup_component

from custom_components.spook.ectoplasms.zone.services import create, update

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def _zones(hass: HomeAssistant, hass_storage: dict[str, Any]) -> None:
    """Set up an editable zone, and register both actions."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {
            "items": [
                {
                    "id": "anchor",
                    "name": "Anchor",
                    "latitude": 52.37,
                    "longitude": 4.89,
                    "radius": 100,
                    "passive": False,
                }
            ]
        },
    }
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    create.SpookService(hass).async_register()
    update.SpookService(hass).async_register()


async def test_a_zone_can_be_created_passive(hass: HomeAssistant) -> None:
    """Discussion #892: a zone only there for an automation, not on the map."""
    await hass.services.async_call(
        DOMAIN,
        "create",
        {"name": "Where I parked", "latitude": 52.1, "longitude": 5.1, "passive": True},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("zone.where_i_parked").attributes["passive"] is True


async def test_a_zone_is_not_passive_unless_asked(hass: HomeAssistant) -> None:
    """Left out, a new zone is an ordinary one."""
    await hass.services.async_call(
        DOMAIN,
        "create",
        {"name": "Office", "latitude": 52.1, "longitude": 5.1},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get("zone.office").attributes["passive"] is False


async def test_a_zone_can_be_made_passive(hass: HomeAssistant) -> None:
    """An existing zone can be switched to passive, and back."""
    for passive in (True, False):
        await hass.services.async_call(
            DOMAIN,
            "update",
            {"entity_id": "zone.anchor", "passive": passive},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hass.states.get("zone.anchor").attributes["passive"] is passive
