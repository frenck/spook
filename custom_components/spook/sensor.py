"""Spook - Not your homey."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from homeassistant.components import automation
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_STARTED,
    EntityCategory,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import HomeAssistantSpookEntity


@dataclass
class HomeAssistantSpookSensorEntityDescriptionMixin:
    """Mixin values for Home Assistant related sensors."""

    value_fn: Callable[[HomeAssistant], int | None]


@dataclass
class HomeAssistantSpookSensorEntityDescription(
    SensorEntityDescription, HomeAssistantSpookSensorEntityDescriptionMixin
):
    """Class describing LaMetric sensor entities."""

    update_events: set[str] = field(default_factory=set)


SENSORS: tuple[HomeAssistantSpookSensorEntityDescription, ...] = (
    HomeAssistantSpookSensorEntityDescription(
        key="automations",
        name="Automations",
        icon="mdi:robot",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        update_events={automation.EVENT_AUTOMATION_RELOADED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(automation.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="entities",
        name="Entities",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids()),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook sensor."""
    async_add_entities(
        HomeAssistantSpookSensorEntity(description) for description in SENSORS
    )


class HomeAssistantSpookSensorEntity(HomeAssistantSpookEntity, SensorEntity):
    """Spook sensor providig Home Asistant information."""

    entity_description: HomeAssistantSpookSensorEntityDescription

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        @callback
        def _update_state(_: Event) -> None:
            """Update state."""
            self.async_schedule_update_ha_state()

        for event in self.entity_description.update_events:
            self.async_on_remove(self.hass.bus.async_listen(event, _update_state))

        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _update_state)
        )

    @property
    def native_value(self) -> int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.hass)
