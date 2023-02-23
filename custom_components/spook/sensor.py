"""Spook - Not your homey."""
from __future__ import annotations

from homeassistant.components import automation, homeassistant
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EntityCategory
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SpookEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook sensor."""
    async_add_entities([SpookAutomationsCountSensorEntity()])


class SpookAutomationsCountSensorEntity(SpookEntity, SensorEntity):
    """Spook sensor providig automation count."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:robot"
    _attr_name = "Automations"
    _attr_should_poll = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self) -> None:
        """Initiate Spook sensor."""
        super().__init__()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, homeassistant.DOMAIN)},
            manufacturer="Home Assistant",
            name="Home Assistant Information",
            sw_version=HA_VERSION,
        )
        self._attr_unique_id = f"{homeassistant.DOMAIN}_automations"

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        @callback
        def _update_state(_: Event) -> None:
            """Update state."""
            self._attr_native_value = len(
                self.hass.states.async_entity_ids(automation.DOMAIN)
            )
            self.async_schedule_update_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(
                automation.EVENT_AUTOMATION_RELOADED, _update_state
            )
        )
        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _update_state)
        )
