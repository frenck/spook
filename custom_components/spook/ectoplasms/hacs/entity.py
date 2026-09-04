"""Spook - Your homie."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo

from ...const import DOMAIN
from ...entity import SpookEntity, SpookEntityDescription

# HACS is a custom integration, not a part of Home Assistant core, so there is
# nothing under `homeassistant.components` to import its domain from. Spelled
# out here rather than imported, so this ectoplasm never needs HACS installed
# to be imported itself, only to do anything.
HACS_DOMAIN = "hacs"


class HACSSpookEntity(SpookEntity):
    """Defines a base Spook entity for HACS related entities."""

    def __init__(self, description: SpookEntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(description=description)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, HACS_DOMAIN)},
            manufacturer="HACS",
            name="HACS",
            configuration_url="https://hacs.xyz/",
        )
        self._attr_unique_id = f"{HACS_DOMAIN}_{description.key}"
