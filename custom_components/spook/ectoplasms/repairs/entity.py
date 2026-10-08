"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.components import repairs
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.loader import async_get_loaded_integration

from ...const import DOMAIN
from ...entity import SpookEntity, SpookEntityDescription


class RepairsSpookEntity(SpookEntity):
    """Defines an base Spook entity for Repairs related entities."""

    def __init__(self, description: SpookEntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(description=description)
        self._attr_unique_id = f"{repairs.DOMAIN}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device, which is Spook's, so it runs Spook's version.

        Read once the entity is added to Home Assistant, as the version comes
        from the loaded integration.
        """
        version = async_get_loaded_integration(self.hass, DOMAIN).version
        return DeviceInfo(
            identifiers={(DOMAIN, repairs.DOMAIN)},
            manufacturer="Spook 👻",
            name="Repairs",
            sw_version=str(version) if version else None,
            configuration_url="https://spook.boo/repairs",
            entry_type=DeviceEntryType.SERVICE,
        )
