"""Spook - Not your homie."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.const import CONF_DEVICE_CLASS, CONF_STATE_TEMPLATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.template import Template, TemplateError
from homeassistant.helpers.template_entity import TemplateEntity
from homeassistant.util.enum import try_parse_enum

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize inverse config entry."""
    async_add_entities([TemplateSensor(hass, config_entry)])


class TemplateSensor(TemplateEntity, SensorEntity):
    """Template sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize an template entity."""
        super().__init__(
            hass,
            fallback_name=config_entry.title,
            unique_id=config_entry.entry_id,
        )
        self._state_template = Template(config_entry.options[CONF_STATE_TEMPLATE], hass)
        self._attr_device_class = try_parse_enum(
            SensorDeviceClass,
            config_entry.options[CONF_DEVICE_CLASS],
        )
        self._attr_native_unit_of_measurement = config_entry.options.get(
            "unit_of_measurement",
        )
        self._attr_state_class = try_parse_enum(
            SensorStateClass,
            config_entry.options.get(CONF_STATE_CLASS),
        )

    async def async_added_to_hass(self) -> None:
        """Adding this entity to hass."""
        self.add_template_attribute(
            "_attr_native_value",
            self._state_template,
            None,
            self._update_state,
        )
        await super().async_added_to_hass()

    @callback
    def _update_state(self, result: str | TemplateError | None) -> None:
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._attr_native_value = None
            return

        if result is None or self.device_class not in (
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        ):
            self._attr_native_value = result
            return

        self._attr_native_value = async_parse_date_datetime(
            result,
            self.entity_id,
            self.device_class,
        )
