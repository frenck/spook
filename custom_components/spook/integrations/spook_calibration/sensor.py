"""Spook - Your homie."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ENTITY_ID,
)
from homeassistant.core import Event, State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)

from .const import CONF_FACTOR, CONF_OFFSET

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_ATTR_STATE_CLASS = "state_class"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize calibration config entry."""
    async_add_entities([CalibrationSensor(hass, config_entry)])


class CalibrationSensor(SensorEntity):  # pylint: disable=too-many-instance-attributes
    """The source's value, corrected: times the factor, plus the offset.

    It takes the source's unit, device class and state class, so a corrected
    temperature graphs and keeps statistics like the temperature it corrects.
    Nothing is restored: the value is worked out from the source every time.
    """

    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        source = config_entry.options[CONF_ENTITY_ID]
        registry = er.async_get(hass)
        self._source = er.async_resolve_entity_id(registry, source) or source

        self._factor = float(config_entry.options[CONF_FACTOR])
        self._offset = float(config_entry.options[CONF_OFFSET])

        self._attr_name = config_entry.title
        self._attr_unique_id = config_entry.entry_id
        self._attr_available = False

        if (
            (source_entry := registry.async_get(self._source))
            and source_entry.device_id
            and (device := dr.async_get(hass).async_get(source_entry.device_id))
        ):
            self.device_entry = device

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the source."""
        return {ATTR_ENTITY_ID: self._source}

    async def async_added_to_hass(self) -> None:
        """Start following the source."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._source, self._async_source_changed
            )
        )
        self._async_take(self.hass.states.get(self._source))

    @callback
    def _async_source_changed(self, event: Event[EventStateChangedData]) -> None:
        """Follow the source into its new value."""
        self.async_set_context(event.context)
        self._async_take(event.data["new_state"])
        self.async_write_ha_state()

    @callback
    def _async_take(self, state: State | None) -> None:
        """Correct the source's value, or be unavailable without one.

        Unavailable, unknown or not a number: there is nothing to correct,
        and making a number up would be worse than saying so. The same goes
        for a correction that comes out as no number.
        """
        if state is None:
            self._attr_available = False
            return

        try:
            value = float(state.state)
        except ValueError:
            self._attr_available = False
            return

        # On the result, not the value: a source at 1e308 times two is a
        # finite number going in and infinity coming out.
        corrected = value * self._factor + self._offset
        if not math.isfinite(corrected):
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_native_value = corrected
        self._attr_native_unit_of_measurement = state.attributes.get(
            ATTR_UNIT_OF_MEASUREMENT
        )
        self._attr_device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        self._attr_state_class = state.attributes.get(_ATTR_STATE_CLASS)
