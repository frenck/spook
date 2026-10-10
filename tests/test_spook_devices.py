"""Tests for the devices Spook adds its entities to."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.loader import async_get_integration

from custom_components.spook.const import DOMAIN
from custom_components.spook.ectoplasms.homeassistant.entity import (
    HomeAssistantSpookEntity,
)
from custom_components.spook.ectoplasms.repairs.entity import RepairsSpookEntity
from custom_components.spook.entity import SpookEntityDescription

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("entity_class", "name", "documentation_url"),
    [
        (
            HomeAssistantSpookEntity,
            "Home Assistant",
            "https://spook.boo/devices-entities",
        ),
        (RepairsSpookEntity, "Repairs", "https://spook.boo/repairs"),
    ],
)
async def test_device_is_spooks_and_runs_its_version(
    hass: HomeAssistant,
    entity_class: type[HomeAssistantSpookEntity | RepairsSpookEntity],
    name: str,
    documentation_url: str,
) -> None:
    """Test the device says Spook made it, and shows Spook's version.

    It used to say Home Assistant made it, and showed Home Assistant's version
    as its firmware, while Spook is what puts it there.
    """
    integration = await async_get_integration(hass, DOMAIN)
    entity = entity_class(SpookEntityDescription(key="test"))
    entity.hass = hass

    device_info = entity.device_info

    assert device_info["manufacturer"] == "Spook 👻"
    assert device_info["name"] == name
    assert device_info["sw_version"] == str(integration.version)
    assert device_info["configuration_url"] == documentation_url
    assert device_info["entry_type"] is DeviceEntryType.SERVICE
