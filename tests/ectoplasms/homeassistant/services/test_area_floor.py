"""Tests for the homeassistant area floor services."""
# pylint: disable=redefined-outer-name

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from homeassistant.components.homeassistant import DOMAIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.spook.ectoplasms.homeassistant.services import add_area_to_floor

if TYPE_CHECKING:
    from homeassistant.helpers.area_registry import AreaRegistry
    from homeassistant.helpers.floor_registry import FloorRegistry

    from tests.common import MockUser


@pytest.fixture
def area_floor_services(hass: HomeAssistant) -> None:
    """Register the Spook area floor services."""
    hass.config.components.add(DOMAIN)
    add_area_to_floor.SpookService(hass).async_register()


@pytest.mark.usefixtures("area_floor_services")
async def test_add_area_to_floor_service_adds_area_to_floor(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    area_registry: AreaRegistry,
    floor_registry: FloorRegistry,
) -> None:
    """Test the add area to floor service adds an area to a floor."""
    area = area_registry.async_create("Kitchen")
    floor = floor_registry.async_create("First floor")

    await hass.services.async_call(
        DOMAIN,
        "add_area_to_floor",
        {"floor_id": floor.floor_id, "area_id": area.id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert area_registry.async_get_area(area.id).floor_id == floor.floor_id


@pytest.mark.usefixtures("area_floor_services")
async def test_add_area_to_floor_service_accepts_multiple_areas(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    area_registry: AreaRegistry,
    floor_registry: FloorRegistry,
) -> None:
    """Test the add area to floor service accepts multiple area IDs."""
    areas = [area_registry.async_create("Kitchen"), area_registry.async_create("Hall")]
    floor = floor_registry.async_create("First floor")

    await hass.services.async_call(
        DOMAIN,
        "add_area_to_floor",
        {"floor_id": floor.floor_id, "area_id": [area.id for area in areas]},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert all(
        area_registry.async_get_area(area.id).floor_id == floor.floor_id
        for area in areas
    )


@pytest.mark.usefixtures("area_floor_services")
async def test_add_area_to_floor_service_raises_on_missing_floor(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    area_registry: AreaRegistry,
) -> None:
    """Test the add area to floor service raises when the floor does not exist."""
    area = area_registry.async_create("Kitchen")

    with pytest.raises(HomeAssistantError, match=re.escape("Floor missing not found")):
        await hass.services.async_call(
            DOMAIN,
            "add_area_to_floor",
            {"floor_id": "missing", "area_id": area.id},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
