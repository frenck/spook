"""Spook - Not your homie."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from homeassistant.components import automation, person, sun, zone
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import HomeAssistantSpookEntity, SpookEntityDescription


@dataclass
class HomeAssistantSpookSensorEntityDescriptionMixin:
    """Mixin values for Home Assistant related sensors."""

    value_fn: Callable[[HomeAssistant], int | None]


@dataclass
class HomeAssistantSpookSensorEntityDescription(
    SpookEntityDescription,
    SensorEntityDescription,
    HomeAssistantSpookSensorEntityDescriptionMixin,
):
    """Class describing Spook Home Assistant sensor entities."""

    update_events: set[str] = field(default_factory=set)


SENSORS: tuple[HomeAssistantSpookSensorEntityDescription, ...] = (
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.AIR_QUALITY,
        entity_id="sensor.air_quality",
        name="Air Quality",
        icon="mdi:air-filter",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.AIR_QUALITY)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.ALARM_CONTROL_PANEL,
        entity_id="sensor.alarm_control_panels",
        name="Alarm control panels",
        icon="mdi:alarm-panel",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(
            hass.states.async_entity_ids(Platform.ALARM_CONTROL_PANEL)
        ),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="area",
        entity_id="sensor.areas",
        name="Areas",
        icon="mdi:texture-box",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, ar.EVENT_AREA_REGISTRY_UPDATED},
        value_fn=lambda hass: len(list(ar.async_get(hass).async_list_areas())),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=automation.DOMAIN,
        entity_id="sensor.automations",
        name="Automations",
        icon="mdi:robot",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={automation.EVENT_AUTOMATION_RELOADED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(automation.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.BINARY_SENSOR,
        entity_id="sensor.binary_sensors",
        name="Binary sensors",
        icon="mdi:numeric-10",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.BINARY_SENSOR)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.BUTTON,
        entity_id="sensor.buttons",
        name="Buttons",
        icon="mdi:gesture-tap",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.BUTTON)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.CALENDAR,
        entity_id="sensor.calendars",
        name="Calendars",
        icon="mdi:calendar",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.CALENDAR)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.CAMERA,
        entity_id="sensor.cameras",
        name="Cameras",
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.CAMERA)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.CLIMATE,
        entity_id="sensor.climate",
        name="Climate",
        icon="mdi:thermostat",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.CLIMATE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.COVER,
        entity_id="sensor.covers",
        name="Covers",
        icon="mdi:blinds",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.COVER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="device",
        entity_id="sensor.devices",
        name="Devices",
        icon="mdi:cellphone",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, dr.EVENT_DEVICE_REGISTRY_UPDATED},
        value_fn=lambda hass: len(dr.async_get(hass).devices),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.DEVICE_TRACKER,
        entity_id="sensor.device_trackers",
        name="Device trackers",
        icon="mdi:cellphone-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(
            hass.states.async_entity_ids(Platform.DEVICE_TRACKER)
        ),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="entities",
        entity_id="sensor.entities",
        name="Entities",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids()),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.FAN,
        entity_id="sensor.fans",
        name="Fans",
        icon="mdi:fan",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.FAN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.HUMIDIFIER,
        entity_id="sensor.humidifiers",
        name="Humidifiers",
        icon="mdi:air-humidifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.HUMIDIFIER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="integration",
        entity_id="sensor.integrations",
        name="Integrations",
        icon="mdi:package-variant-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED},
        value_fn=lambda hass: len(hass.data["entity_platform"]),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="custom_component",
        entity_id="sensor.custom_integrations",
        name="Custom integrations",
        icon="mdi:package-variant-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED},
        value_fn=lambda hass: len(hass.data["custom_components"]),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.LIGHT,
        entity_id="sensor.lights",
        name="Lights",
        icon="mdi:lightbulb",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.LIGHT)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.LOCK,
        entity_id="sensor.locks",
        name="Locks",
        icon="mdi:lock",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.LOCK)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.MEDIA_PLAYER,
        entity_id="sensor.media_players",
        name="Media players",
        icon="mdi:record-player",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.NUMBER,
        entity_id="sensor.numbers",
        name="Numbers",
        icon="mdi:ray-vertex",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.NUMBER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=person.DOMAIN,
        entity_id="sensor.persons",
        name="Persons",
        icon="mdi:account-group",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(person.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.REMOTE,
        entity_id="sensor.remotes",
        name="Remotes",
        icon="mdi:remote",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.REMOTE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SCENE,
        entity_id="sensor.scenes",
        name="Scenes",
        icon="mdi:palette",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SCENE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SELECT,
        entity_id="sensor.selects",
        name="Selects",
        icon="mdi:format-list-bulleted",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SELECT)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SENSOR,
        entity_id="sensor.sensors",
        name="Sensors",
        icon="mdi:eye",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SENSOR)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SIREN,
        entity_id="sensor.sirens",
        name="Sirens",
        icon="mdi:bullhorn",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SIREN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=sun.DOMAIN,
        entity_id="sensor.suns",
        name="Suns",
        icon="mdi:emoticon-cool",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(sun.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SWITCH,
        entity_id="sensor.switches",
        name="Switches",
        icon="mdi:toggle-switch",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SWITCH)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.TEXT,
        entity_id="sensor.texts",
        name="Texts",
        icon="mdi:form-textbox",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.TEXT)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.VACUUM,
        entity_id="sensor.vacuums",
        name="Vacuums",
        icon="mdi:vacuum",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.VACUUM)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.UPDATE,
        entity_id="sensor.update",
        name="Update",
        icon="mdi:cellphone-arrow-down",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.UPDATE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.WATER_HEATER,
        entity_id="sensor.water_heaters",
        name="Water heaters",
        icon="mdi:water-boiler",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.WATER_HEATER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.WEATHER,
        entity_id="sensor.weather",
        name="Weather",
        icon="mdi:weather-cloudy",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.WEATHER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=zone.DOMAIN,
        entity_id="sensor.zones",
        name="Zones",
        icon="mdi:selection-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(zone.DOMAIN)),
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
