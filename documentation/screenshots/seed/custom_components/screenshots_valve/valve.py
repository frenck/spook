"""The garden tap: a valve that remembers how far it is open."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.valve import ValveEntity, ValveEntityFeature

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_platform(
    _hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the garden tap from YAML."""
    async_add_entities([GardenTap(config["name"])])


class GardenTap(ValveEntity):
    """A valve that goes where it is told, right away."""

    _attr_reports_position = True
    _attr_should_poll = False
    _attr_supported_features = (
        ValveEntityFeature.OPEN
        | ValveEntityFeature.CLOSE
        | ValveEntityFeature.SET_POSITION
    )
    # So the setup can give it its name in the language of the screenshots.
    _attr_unique_id = "garden_tap"

    def __init__(self, name: str) -> None:
        """Start half open."""
        self._attr_name = name
        self._attr_current_valve_position = 50

    async def async_set_valve_position(self, position: int) -> None:
        """Turn the tap."""
        self._attr_current_valve_position = position
        self.async_write_ha_state()
