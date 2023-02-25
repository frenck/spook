"""Spook - Not your homie."""
from __future__ import annotations

from dataclasses import dataclass

from hass_nabucasa import Cloud

from homeassistant.components import homeassistant
from homeassistant.components.cloud.const import DOMAIN as CLOUD_DOMAIN
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


class HomeAssistantCloudSpookEntity(SpookEntity):
    """Defines an base Spook entity for Home Assistant Cloud related entities."""

    _cloud: Cloud

    def __init__(self, cloud: Cloud, description: SpookEntityDescription) -> None:
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
