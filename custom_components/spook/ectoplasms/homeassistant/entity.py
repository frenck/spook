"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import homeassistant
from homeassistant.const import __version__
from homeassistant.helpers.device_registry import DeviceInfo

from ...const import DOMAIN
from ...entity import SpookEntity, SpookEntityDescription


class HomeAssistantSpookEntity(SpookEntity):
    """Defines an base Spook entity for Home Assistant related entities."""

    def __init__(self, description: SpookEntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(description=description)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, homeassistant.DOMAIN)},
            manufacturer="Home Assistant",
            name="Home Assistant",
            sw_version=__version__,
        )
        self._attr_unique_id = f"{homeassistant.DOMAIN}_{description.key}"
