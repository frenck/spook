"""Spook - Not your homey."""
from __future__ import annotations

from homeassistant.components import automation, homeassistant
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_STARTED,
    EntityCategory,
    __version__ as HA_VERSION,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .entity import SpookEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook sensor."""
    async_add_entities(
        [
            SpookAutomationsCountSensorEntity(),
            SpookEntityCountSensorEntity(),
        ]
    )


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


class SpookEntityCountSensorEntity(SpookEntity, SensorEntity):
    """Spook sensor providig entity count."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:counter"
    _attr_name = "Entities"
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
        self._attr_unique_id = f"{homeassistant.DOMAIN}_entities"

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        @callback
        def _update_state(_: Event) -> None:
            """Update state."""
            self.async_schedule_update_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_COMPONENT_LOADED, _update_state)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(er.EVENT_ENTITY_REGISTRY_UPDATED, _update_state)
        )
        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _update_state)
        )

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return len(self.hass.states.async_entity_ids())
