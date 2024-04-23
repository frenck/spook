"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.cloud.const import DOMAIN as CLOUD_DOMAIN
from homeassistant.helpers.device_registry import DeviceInfo

from ...const import DOMAIN
from ...entity import SpookEntity, SpookEntityDescription

if TYPE_CHECKING:
    from hass_nabucasa import Cloud

    from homeassistant.components.cloud.client import CloudClient


class HomeAssistantCloudSpookEntity(SpookEntity):
    """Defines an base Spook entity for Home Assistant Cloud related entities."""

    def __init__(
        self, cloud: Cloud[CloudClient], description: SpookEntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(description=description)
        self._cloud = cloud
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, CLOUD_DOMAIN)},
            manufacturer="Nabu Casa Inc.",
            name="Home Assistant Cloud",
            configuration_url="https://account.nabucasa.com/",
        )
        self._attr_unique_id = f"{CLOUD_DOMAIN}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if cloud services are available."""
        return (
            super().available and self._cloud.is_logged_in and self._cloud.is_connected
        )
