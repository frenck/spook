"""Spook - Not your homey."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components import homeassistant
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityDescription

from .const import DOMAIN


@dataclass
class SpookEntityDescription(EntityDescription):
    """Defines an base Spook entity description."""

    entity_id: str | None = None


class SpookEntity(Entity):
    """Defines an base Spook entity."""

    entity_description: SpookEntityDescription

    _attr_has_entity_name = True

    def __init__(self, description: SpookEntityDescription) -> None:
        """Initialize the entity."""
        self.entity_description = description
        if description.entity_id:
            self.entity_id = description.entity_id


class HomeAssistantSpookEntity(SpookEntity):
    """Defines an base Spook entity for Home Assistant related entities."""

    def __init__(self, description: SpookEntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(description=description)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, homeassistant.DOMAIN)},
            manufacturer="Home Assistant",
            name="Home Assistant Information",
            sw_version=HA_VERSION,
        )
        self._attr_unique_id = f"{homeassistant.DOMAIN}_{description.key}"
