"""Spook - Your homie."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import CONF_ENTITY_ID, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er

from .entity import InverseEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize inverse config entry."""
    er.async_validate_entity_id(
        er.async_get(hass),
        config_entry.options[CONF_ENTITY_ID],
    )
    async_add_entities([InverseBinarySensor(config_entry)])


class InverseBinarySensor(InverseEntity, BinarySensorEntity):
    """Inverse binary sensor."""

    @callback
    def async_update_state(self, state: State) -> None:
        """Query the source and determine the binary sensor state."""
        if state.state == STATE_UNKNOWN:
            self._attr_is_on = None
        else:
            self._attr_is_on = state.state != STATE_ON
