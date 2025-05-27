"""Spook - Your homie."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from homeassistant.components import (
    automation,
    input_boolean,
    input_button,
    input_datetime,
    input_number,
    input_select,
    input_text,
    persistent_notification,
    person,
    script,
    sun,
    zone,
)
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_STARTED,
    EntityCategory,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later

from ...entity import SpookEntityDescription
from .entity import HomeAssistantSpookEntity

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime  # Moved datetime here

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.util.event_type import EventType


@dataclass(frozen=True, kw_only=True)
class HomeAssistantSpookSensorEntityDescription(
    SpookEntityDescription,
    SensorEntityDescription,
):
    """Class describing Spook Home Assistant sensor entities."""

    value_fn: Callable[[HomeAssistant], int | None]
    update_events: set[EventType[Any] | str] = field(default_factory=set)


SENSORS: tuple[HomeAssistantSpookSensorEntityDescription, ...] = (
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.AIR_QUALITY,
        translation_key="homeassistant_air_quality",
        entity_id="sensor.air_quality",
        icon="mdi:air-filter",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.AIR_QUALITY)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.ALARM_CONTROL_PANEL,
        translation_key="homeassistant_alarm_control_panel",
        entity_id="sensor.alarm_control_panels",
        icon="mdi:alarm-panel",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(
            hass.states.async_entity_ids(Platform.ALARM_CONTROL_PANEL),
        ),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="area",
        translation_key="homeassistant_area",
        entity_id="sensor.areas",
        icon="mdi:texture-box",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, ar.EVENT_AREA_REGISTRY_UPDATED},
        value_fn=lambda hass: len(list(ar.async_get(hass).async_list_areas())),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=automation.DOMAIN,
        translation_key="homeassistant_automation",
        entity_id="sensor.automations",
        icon="mdi:robot",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={automation.EVENT_AUTOMATION_RELOADED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(automation.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.BINARY_SENSOR,
        translation_key="homeassistant_binary_sensor",
        entity_id="sensor.binary_sensors",
        icon="mdi:numeric-10",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.BINARY_SENSOR)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.BUTTON,
        translation_key="homeassistant_button",
        entity_id="sensor.buttons",
        icon="mdi:gesture-tap",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.BUTTON)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.CALENDAR,
        translation_key="homeassistant_calendar",
        entity_id="sensor.calendars",
        icon="mdi:calendar",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.CALENDAR)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.CAMERA,
        translation_key="homeassistant_camera",
        entity_id="sensor.cameras",
        icon="mdi:cctv",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.CAMERA)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.CLIMATE,
        translation_key="homeassistant_climate",
        entity_id="sensor.climate",
        icon="mdi:thermostat",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.CLIMATE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.COVER,
        translation_key="homeassistant_cover",
        entity_id="sensor.covers",
        icon="mdi:blinds",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.COVER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.DATE,
        translation_key="homeassistant_date",
        entity_id="sensor.dates",
        icon="mdi:calendar-month-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.DATE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.DATETIME,
        translation_key="homeassistant_datetime",
        entity_id="sensor.datetimes",
        icon="mdi:calendar-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.DATETIME)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="device",
        translation_key="homeassistant_device",
        entity_id="sensor.devices",
        icon="mdi:cellphone",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, dr.EVENT_DEVICE_REGISTRY_UPDATED},
        value_fn=lambda hass: len(dr.async_get(hass).devices),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.DEVICE_TRACKER,
        translation_key="homeassistant_device_tracker",
        entity_id="sensor.device_trackers",
        icon="mdi:cellphone-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(
            hass.states.async_entity_ids(Platform.DEVICE_TRACKER),
        ),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="entities",
        translation_key="homeassistant_entities",
        entity_id="sensor.entities",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids()),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.FAN,
        translation_key="homeassistant_fan",
        entity_id="sensor.fans",
        icon="mdi:fan",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.FAN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.HUMIDIFIER,
        translation_key="homeassistant_humidifier",
        entity_id="sensor.humidifiers",
        icon="mdi:air-humidifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.HUMIDIFIER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="integration",
        translation_key="homeassistant_integration",
        entity_id="sensor.integrations",
        icon="mdi:package-variant-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED},
        value_fn=lambda hass: len(hass.data["entity_platform"]),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="custom_component",
        translation_key="homeassistant_custom_component",
        entity_id="sensor.custom_integrations",
        icon="mdi:package-variant-closed",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED},
        value_fn=lambda hass: len(hass.data["custom_components"]),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=input_boolean.DOMAIN,
        translation_key="homeassistant_input_boolean",
        entity_id="sensor.input_booleans",
        icon="mdi:toggle-switch-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(input_boolean.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=input_button.DOMAIN,
        translation_key="homeassistant_input_button",
        entity_id="sensor.input_buttons",
        icon="mdi:gesture-tap-button",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(input_button.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=input_datetime.DOMAIN,
        translation_key="homeassistant_input_datetime",
        entity_id="sensor.input_datetimes",
        icon="mdi:clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(input_datetime.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=input_number.DOMAIN,
        translation_key="homeassistant_input_number",
        entity_id="sensor.input_numbers",
        icon="mdi:ray-vertex",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(input_number.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=input_select.DOMAIN,
        translation_key="homeassistant_input_select",
        entity_id="sensor.input_selects",
        icon="mdi:form-dropdown",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(input_select.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=input_text.DOMAIN,
        translation_key="homeassistant_input_text",
        entity_id="sensor.input_texts",
        icon="mdi:form-textbox",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(input_text.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.IMAGE,
        translation_key="homeassistant_image",
        entity_id="sensor.images",
        icon="mdi:image",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.IMAGE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.LIGHT,
        translation_key="homeassistant_light",
        entity_id="sensor.lights",
        icon="mdi:lightbulb",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.LIGHT)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.LOCK,
        translation_key="homeassistant_lock",
        entity_id="sensor.locks",
        icon="mdi:lock",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.LOCK)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.MEDIA_PLAYER,
        translation_key="homeassistant_media_player",
        entity_id="sensor.media_players",
        icon="mdi:record-player",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.MEDIA_PLAYER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.NUMBER,
        translation_key="homeassistant_number",
        entity_id="sensor.numbers",
        icon="mdi:ray-vertex",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.NUMBER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key="persistent_notification",
        translation_key="homeassistant_persistent_notification",
        entity_id="sensor.persistent_notifications",
        icon="mdi:bell-ring-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={
            "persistent_notifications_updated",
        },
        value_fn=lambda hass: len(
            # pylint: disable-next=protected-access
            persistent_notification._async_get_or_create_notifications(  # noqa: SLF001
                hass,
            ),
        ),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=person.DOMAIN,
        translation_key="homeassistant_person",
        entity_id="sensor.persons",
        icon="mdi:account-group",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(person.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.REMOTE,
        translation_key="homeassistant_remote",
        entity_id="sensor.remotes",
        icon="mdi:remote",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.REMOTE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SCENE,
        translation_key="homeassistant_scene",
        entity_id="sensor.scenes",
        icon="mdi:palette",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SCENE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=script.DOMAIN,
        translation_key="homeassistant_script",
        entity_id="sensor.scripts",
        icon="mdi:script-text",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(script.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SELECT,
        translation_key="homeassistant_select",
        entity_id="sensor.selects",
        icon="mdi:format-list-bulleted",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SELECT)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SENSOR,
        translation_key="homeassistant_sensor",
        entity_id="sensor.sensors",
        icon="mdi:eye",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SENSOR)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SIREN,
        translation_key="homeassistant_siren",
        entity_id="sensor.sirens",
        icon="mdi:bullhorn",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SIREN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=sun.DOMAIN,
        translation_key="homeassistant_sun",
        entity_id="sensor.suns",
        icon="mdi:emoticon-cool",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(sun.DOMAIN)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.STT,
        translation_key="homeassistant_stt",
        entity_id="sensor.stt",
        icon="mdi:microphone-message",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.STT)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.SWITCH,
        translation_key="homeassistant_switch",
        entity_id="sensor.switches",
        icon="mdi:toggle-switch",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.SWITCH)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.TEXT,
        translation_key="homeassistant_text",
        entity_id="sensor.texts",
        icon="mdi:form-textbox",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.TEXT)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.TIME,
        translation_key="homeassistant_time",
        entity_id="sensor.times",
        icon="mdi:clock-time-eight-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.TIME)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.TTS,
        translation_key="homeassistant_tts",
        entity_id="sensor.tts",
        icon="mdi:speaker-message",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.TTS)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.VACUUM,
        translation_key="homeassistant_vacuum",
        entity_id="sensor.vacuums",
        icon="mdi:vacuum",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.VACUUM)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.UPDATE,
        translation_key="homeassistant_update",
        entity_id="sensor.update",
        icon="mdi:cellphone-arrow-down",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.UPDATE)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.WATER_HEATER,
        translation_key="homeassistant_water_heater",
        entity_id="sensor.water_heaters",
        icon="mdi:water-boiler",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.WATER_HEATER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=Platform.WEATHER,
        translation_key="homeassistant_weather",
        entity_id="sensor.weather",
        icon="mdi:weather-cloudy",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(Platform.WEATHER)),
    ),
    HomeAssistantSpookSensorEntityDescription(
        key=zone.DOMAIN,
        translation_key="homeassistant_zone",
        entity_id="sensor.zones",
        icon="mdi:selection-marker",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        update_events={EVENT_COMPONENT_LOADED, er.EVENT_ENTITY_REGISTRY_UPDATED},
        value_fn=lambda hass: len(hass.states.async_entity_ids(zone.DOMAIN)),
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    _entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Spook sensor."""
    async_add_entities(
        HomeAssistantSpookSensorEntity(description) for description in SENSORS
    )


class HomeAssistantSpookSensorEntity(HomeAssistantSpookEntity, SensorEntity):
    """Spook sensor providig Home Asistant information."""

    entity_description: HomeAssistantSpookSensorEntityDescription
    _unsub_debouncer: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""

        @callback
        def _debounced_update(
            _now: datetime | None = None,
        ) -> None:
            """Update state after debounce."""
            self._unsub_debouncer = None
            self.async_schedule_update_ha_state()

        @callback
        def _update_state(_: Event) -> None:
            """Update state."""
            if self._unsub_debouncer:
                self._unsub_debouncer()
            self._unsub_debouncer = async_call_later(self.hass, 5, _debounced_update)

        for event in self.entity_description.update_events:
            self.async_on_remove(self.hass.bus.async_listen(event, _update_state))

        self.async_on_remove(
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _update_state),
        )

    async def async_will_remove_from_hass(self) -> None:
        """Clean up debounce timer."""
        if self._unsub_debouncer:
            self._unsub_debouncer()
            self._unsub_debouncer = None
        await super().async_will_remove_from_hass()

    @property
    def native_value(self) -> int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.hass)
