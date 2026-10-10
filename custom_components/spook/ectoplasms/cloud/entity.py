"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo

from ...const import DOMAIN
from ...entity import SpookEntity, SpookEntityDescription

if TYPE_CHECKING:
    from hass_nabucasa import Cloud

    from homeassistant.components.cloud.client import CloudClient

# Spelled out rather than imported. Importing anything from the cloud
# integration runs its package first, and that pulls in Alexa, Google
# Assistant and camera with it, on the single import thread, at startup,
# for a house that may not use the cloud at all. #1898.
CLOUD_DOMAIN = "cloud"


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
