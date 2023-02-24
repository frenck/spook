"""Spook - Not your homey."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.components import homeassistant
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN


class SpookEntity(Entity):
    """Defines an base Spook entity."""

    _attr_has_entity_name = True

    def __init__(self, description: EntityDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description


class HomeAssistantSpookEntity(SpookEntity):
    """Defines an base Spook entity for Home Assistant related entities."""

    def __init__(self, description: EntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(description=description)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, homeassistant.DOMAIN)},
            manufacturer="Home Assistant",
            name="Home Assistant Information",
            sw_version=HA_VERSION,
        )
        self._attr_unique_id = f"{homeassistant.DOMAIN}_{description.key}"
