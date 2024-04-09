"""Spook - Your homie."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.start import async_at_start

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry


class InverseEntity(Entity):  # pylint: disable=too-many-instance-attributes
    """Inverse entity."""

    _attr_available = False
    _attr_should_poll = False

    def __init__(
        self,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize an inverse entity."""
        super().__init__()
        self._entity_id = config_entry.options[CONF_ENTITY_ID]
        self._attr_name = config_entry.title
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: self._entity_id}
        self._attr_unique_id = config_entry.entry_id
        self.config_entry = config_entry

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        entity_registry = er.async_get(self.hass)
        device_registry = dr.async_get(self.hass)
        source_entity = entity_registry.async_get(self._entity_id)
        if (
            (source_entity is not None)
            and (source_entity.device_id is not None)
            and (
                (
                    device := device_registry.async_get(
                        device_id=source_entity.device_id,
                    )
                )
                is not None
            )
        ):
            return DeviceInfo(
                identifiers=device.identifiers,
                connections=device.connections,
            )
        return None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                self._entity_id,
                self.async_update_and_write_state,
            ),
        )

        async def async_update_at_start(_: HomeAssistant) -> None:
            """Update the state at startup."""
            self.async_update_and_write_state()

        self.async_on_remove(async_at_start(self.hass, async_update_at_start))

        await super().async_added_to_hass()

    @callback
    def async_update_and_write_state(
        self,
        event: Event[EventStateChangedData] | None = None,
    ) -> None:
        """Update the state and write it to the entity."""
        if not self.hass.is_running:
            return

        if event is not None:
            self.async_set_context(event.context)

        if (
            state := self.hass.states.get(self._entity_id)
        ) is None or state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_supported_features = state.attributes.get(ATTR_SUPPORTED_FEATURES)
        self._attr_device_class = state.attributes.get(ATTR_DEVICE_CLASS)
        self._attr_icon = state.attributes.get(ATTR_ICON)

        self.async_update_state(state)

        state_attributes = {
            **self._attr_extra_state_attributes,
            ATTR_ENTITY_ID: self._entity_id,
        }
        state_attributes.pop(ATTR_ICON, None)
        state_attributes.pop(ATTR_DEVICE_CLASS, None)
        state_attributes.pop(ATTR_SUPPORTED_FEATURES, None)
        self._attr_extra_state_attributes = state_attributes

        self.async_write_ha_state()

    @abstractmethod
    @callback
    def async_update_state(self, state: State) -> None:
        """Query the source and determine the entity state."""
